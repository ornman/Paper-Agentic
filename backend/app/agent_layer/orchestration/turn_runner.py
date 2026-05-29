"""核心编排器：一轮请求的状态机"""

from __future__ import annotations

import json
import inspect
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any, Protocol

from openai import APIConnectionError, APIStatusError, RateLimitError

from app.agent_layer.contracts.query import AskRequest
from app.agent_layer.contracts.sse_events import (
    BlockEvent,
    DoneEvent,
    ErrorEvent,
    MetadataEvent,
    ReflectionEvent,
    SourcesEvent,
    ThinkingEvent,
)
from app.agent_layer.runtime.token_budget import estimate_tokens
from app.data_layer.retrieval.fusion.rrf_fusion import rrf_fuse
from app.agent_layer.hooks.compact import compact_conversation
from app.agent_layer.hooks.reflection import judge_evidence
from app.agent_layer.orchestration.tool_loop import (
    ToolLoopEvent,
    ToolRegistry,
    execute_tool_loop,
)
from app.agent_layer.runtime.chat_model import ChatModel
from app.agent_layer.runtime.token_budget import TokenBudget
from app.agent_layer.session.editor_context_store import EditorContextStore
from app.agent_layer.session.persistence import SessionPersistence
from app.agent_layer.session.window_store import ConversationWindowStore

logger = logging.getLogger("paper-assistant")


class VectorStoreProtocol(Protocol):
    def query(self, vector: list[float], topk: int, paper_ids: list[str] | None = None) -> list: ...


class KeywordSearchProtocol(Protocol):
    def query(self, query_text: str, topk: int, paper_ids: list[str] | None = None) -> list: ...


class EmbeddingClientProtocol(Protocol):
    async def embed_single(self, text: str) -> list[float]: ...


class SnapshotBuilder(Protocol):
    def __call__(self, request: Any, editor_context: Any, recent_window: list, history_summary: str) -> Any: ...


class RetrievalGate(Protocol):
    def __call__(self, snapshot: Any) -> bool: ...


class SourceMapper(Protocol):
    def __call__(self, retrieval_results: list[dict]) -> list: ...


class BlockStreamer(Protocol):
    def __call__(self, text: str, sources: list) -> list: ...


def _user_friendly_error(exc: Exception) -> dict:
    """将内部异常转换为用户友好的错误载荷，不暴露内部细节"""
    if isinstance(exc, RateLimitError):
        return {
            "message": "当前请求量较大，请稍后再试",
            "code": "rate_limit",
            "retryable": True,
            "suggested_action": "请稍后重试",
        }
    if isinstance(exc, APIConnectionError):
        return {
            "message": "无法连接到 AI 服务，请检查网络后重试",
            "code": "connection",
            "retryable": True,
            "suggested_action": "请检查网络",
        }
    if isinstance(exc, APIStatusError):
        if exc.status_code >= 500:
            return {
                "message": "AI 服务暂时不可用，请稍后再试",
                "code": "server_error",
                "retryable": True,
            }
        return {
            "message": f"请求被拒绝（状态码 {exc.status_code}）",
            "code": "client_error",
            "retryable": False,
        }
    if isinstance(exc, TimeoutError):
        return {
            "message": "请求超时，请稍后再试",
            "code": "timeout",
            "retryable": True,
            "suggested_action": "请稍后重试",
        }
    return {
        "message": "处理请求时出现错误，请稍后再试",
        "code": "unknown",
        "retryable": False,
    }


_RAG_SYSTEM_PROMPT = """你是一个有帮助的学术写作助手。请用中文回答用户的问题。

你必须基于提供的资料回答。
- 只在有证据时下结论，不要编造来源
- 回答中引用证据时，使用 [N] 格式标注来源编号（如 [1]、[2][3]）
- 编号必须对应提供给你的来源顺序
- 优先把结论写清楚，再用编号引用支撑，不要输出文件 hash 或内部 ID

{context}
"""

_NO_RAG_SYSTEM_PROMPT = """你是一个有帮助的学术写作助手。请用中文回答用户的问题。
回答要求：准确、简洁、有条理。如果不确定，坦诚说明。"""


class TurnRunner:
    def __init__(
        self,
        chat_model: ChatModel,
        snapshot_builder: SnapshotBuilder,
        retrieval_gate: RetrievalGate,
        source_mapper: SourceMapper,
        block_streamer: BlockStreamer,
        window_store: ConversationWindowStore,
        editor_context_store: EditorContextStore,
        persistence: SessionPersistence,
        vector_store: VectorStoreProtocol | None = None,
        keyword_search: KeywordSearchProtocol | None = None,
        embedding_client: EmbeddingClientProtocol | None = None,
        tool_registry: ToolRegistry | None = None,
        cache_mode: str = "memory",
        reflection_model: ChatModel | None = None,
    ) -> None:
        self._chat_model = chat_model
        self._reflection_model = reflection_model
        self._snapshot_builder = snapshot_builder
        self._retrieval_gate = retrieval_gate
        self._source_mapper = source_mapper
        self._block_streamer = block_streamer
        self._window_store = window_store
        self._editor_context_store = editor_context_store
        self._persistence = persistence
        self._vector_store = vector_store
        self._keyword_search = keyword_search
        self._embedding_client = embedding_client
        self._tool_registry = tool_registry
        self._cache_mode = cache_mode

    async def run(self, request: AskRequest) -> AsyncIterator[str]:
        request_id = uuid.uuid4().hex

        try:
            if not request.prompt or not request.prompt.strip():
                yield ErrorEvent(message="请提供问题或内容").to_sse_frame()
                return

            snapshot = await self._freeze_snapshot(request, request_id)

            # ── Metadata 事件：首个 SSE 帧，报告输入源和 token 预算 ──
            degraded_flags: list[str] = []
            if self._editor_context_store is None:
                degraded_flags.append("editor_context_unavailable")
            if self._window_store is None:
                degraded_flags.append("window_store_unavailable")

            context_tokens = estimate_tokens(
                (snapshot.prompt or "")
                + (snapshot.selection or "")
                + (snapshot.written_context or "")
                + (snapshot.history_summary or "")
            )
            try:
                max_context = int(getattr(self._chat_model, "max_context_tokens", 30000))
            except (TypeError, ValueError):
                max_context = 30000
            remaining_tokens = max(0, max_context - context_tokens)
            remaining_ratio = remaining_tokens / max_context if max_context > 0 else 0.0
            compacted = False

            # ── Compact：剩余空间不足时压缩历史 ──
            # 注意：FrozenTurnSnapshot 是 Pydantic BaseModel，默认 frozen=False 允许属性赋值。
            # 若后续改为 frozen=True，此处需要用 model_copy(update=...) 替代直接赋值。
            if remaining_ratio < 0.05 and snapshot.recent_window:
                compact_result = await compact_conversation(
                    self._chat_model, snapshot.recent_window,
                    max_context_tokens=max_context,
                )
                if compact_result.summary:
                    snapshot.history_summary = compact_result.summary
                    snapshot.recent_window = []
                    compacted = True
                    if compact_result.degraded:
                        degraded_flags.append(f"compact_degraded:{compact_result.degrade_reason}")
                    # 重新计算 token 用量
                    context_tokens = estimate_tokens(
                        (snapshot.prompt or "")
                        + (snapshot.selection or "")
                        + (snapshot.written_context or "")
                        + (snapshot.history_summary or "")
                    )
                    remaining_tokens = max(0, max_context - context_tokens)
                    remaining_ratio = remaining_tokens / max_context if max_context > 0 else 0.0

            yield MetadataEvent(
                request_id=snapshot.request_id,
                session_id=snapshot.session_id,
                used_inputs=snapshot.used_inputs.model_dump(),
                context_tokens=context_tokens,
                remaining_tokens=remaining_tokens,
                remaining_ratio=round(remaining_ratio, 4),
                retrieval_planned=snapshot.enable_rag,
                degraded_flags=degraded_flags,
                cache_mode=self._cache_mode,
            ).to_sse_frame()

            query_text = self._assemble_query(snapshot)

            need_rag = self._retrieval_gate(snapshot)

            retrieval_results: list[dict] = []
            sources: list = []
            context = ""

            if need_rag:
                from app.service_layer.config.settings import get_settings
                _settings = get_settings()
                max_reflection_rounds = _settings.reflection_max_rounds
                max_direction_switches = _settings.reflection_max_direction_switches
                direction_switches = 0
                current_query = query_text
                current_topk = 0  # 0 = 不限制，由 TokenBudget 动态裁剪

                for round_num in range(1, max_reflection_rounds + 1):
                    retrieval_results = await self._retrieve(
                        current_query, snapshot.paper_ids, topk=current_topk
                    )
                    sources = self._source_mapper(retrieval_results)
                    context = self._build_context(retrieval_results)

                    if not snapshot.reflection_enabled or not context:
                        break

                    judgment = await judge_evidence(self._chat_model, current_query, context, judge_model=self._reflection_model)
                    yield ReflectionEvent(
                        round=round_num,
                        verdict=judgment.verdict,
                        reason=judgment.reason,
                    ).to_sse_frame()

                    if judgment.verdict == "supported":
                        break

                    if judgment.verdict in ("off_track", "conflicting"):
                        direction_switches += 1
                        if direction_switches >= max_direction_switches:
                            break
                        current_query = f"{query_text} {judgment.reason}"

                    if judgment.verdict == "insufficient":
                        # 沿当前方向深挖：扩大检索范围
                        current_topk = min(current_topk * 2, 50)

            messages = self._build_messages(snapshot, context)

            if snapshot.thinking_enabled:
                yield ThinkingEvent(text="", time_ms=0).to_sse_frame()

            full_text = ""
            model_override = snapshot.model_name or None
            async for chunk in self._chat_model.chat_stream(messages, model=model_override):
                full_text += chunk

            # ── Tool Loop：LLM 可决定调用内部工具 ──
            if self._tool_registry and self._tool_registry.tool_names:
                from app.agent_layer.orchestration.tool_loop import execute_tool_loop

                async def _llm_decide(msgs: list[dict]):
                    # 让 LLM 判断是否需要工具调用
                    tool_prompt = msgs + [{"role": "system", "content":
                        f"你可以调用以下工具：{self._tool_registry.tool_names}。"
                        "如果需要调用工具，返回 JSON：{\"name\": \"工具名\", \"arguments\": {...}}。"
                        "如果不需要调用工具，直接回答用户问题即可，不要返回 JSON。"
                    }]
                    resp = await self._chat_model.chat(tool_prompt)
                    import json as _json
                    try:
                        data = _json.loads(resp.strip())
                        if "name" in data:
                            from app.agent_layer.orchestration.tool_loop import ToolCall
                            return ToolCall(name=data["name"], arguments=data.get("arguments", {}))
                    except (_json.JSONDecodeError, ValueError):
                        pass
                    return None  # 不需要工具调用

                tool_result = await execute_tool_loop(
                    llm_decide=_llm_decide,
                    initial_messages=messages,
                    registry=self._tool_registry,
                )
                if tool_result.rounds_used > 0:
                    # 工具调用有结果，用工具输出作为最终回答
                    full_text = tool_result.final_output

            blocks = self._block_streamer(full_text, sources)
            for block in blocks:
                yield BlockEvent(data=block).to_sse_frame()

            yield SourcesEvent(data=sources).to_sse_frame()

            await self._persist(snapshot, full_text, blocks, sources, compacted=compacted)

            yield DoneEvent().to_sse_frame()

        except Exception as exc:
            logger.exception("Turn execution failed: %s", exc)
            err = _user_friendly_error(exc)
            yield ErrorEvent(**err).to_sse_frame()

    async def _freeze_snapshot(self, request: AskRequest, request_id: str) -> Any:
        editor_context = None
        freeze_fn = getattr(self._editor_context_store, "freeze", None)
        if callable(freeze_fn):
            try:
                frozen_context = freeze_fn(request.session_id, request_id)
                if inspect.isawaitable(frozen_context):
                    frozen_context = await frozen_context
                editor_context = frozen_context
            except Exception:
                logger.warning(
                    "editor_context freeze failed for session %s",
                    request.session_id,
                    exc_info=True,
                )
        if editor_context is None:
            editor_context = await self._editor_context_store.get(request.session_id)
        recent_window = await self._window_store.get_messages(request.session_id)
        history_summary = await self._persistence.get_summary(request.session_id) or ""

        return self._snapshot_builder(
            request=request,
            editor_context=editor_context,
            recent_window=recent_window,
            history_summary=history_summary,
        )

    def _assemble_query(self, snapshot: Any) -> str:
        """根据 used_inputs 权重组装查询文本，权重高的排在前面"""
        weights = snapshot.used_inputs
        parts: list[tuple[float, str]] = []

        if snapshot.prompt:
            parts.append((weights.prompt, snapshot.prompt))
        if snapshot.selection:
            parts.append((weights.selection, f"用户圈选的文本：{snapshot.selection}"))
        if snapshot.written_context:
            parts.append((weights.written_context, f"用户已写内容：{snapshot.written_context}"))

        parts.sort(key=lambda x: x[0], reverse=True)
        return "\n\n".join(text for _, text in parts)

    async def _retrieve(
        self, query_text: str, paper_ids: list[str] | None, topk: int = 0
    ) -> list[dict]:
        """检索：取候选 → RRF 融合 → 返回

        topk=0 时融合不限数量，由 _build_context 的 TokenBudget 动态裁剪。
        """
        from app.service_layer.config.settings import get_settings
        _s = get_settings()
        dense_results = []
        sparse_results = []

        if self._embedding_client is not None and self._vector_store is not None:
            try:
                query_vector = await self._embedding_client.embed_single(query_text)
                dense_results = self._vector_store.query(query_vector, topk=_s.retrieval_topk_dense, paper_ids=paper_ids)
            except Exception as exc:
                logger.warning("Dense retrieval failed: %s", exc)

        if self._keyword_search is not None:
            try:
                sparse_results = self._keyword_search.query(query_text, topk=_s.retrieval_topk_sparse, paper_ids=paper_ids)
            except Exception as exc:
                logger.warning("Keyword retrieval failed: %s", exc)

        if not dense_results and not sparse_results:
            return []

        fused = rrf_fuse(dense_results, sparse_results, topk=topk or len(dense_results) + len(sparse_results), keyword_index=self._keyword_search, rrf_k=_s.retrieval_rrf_k)
        return [
            {
                "content": doc.content,
                "paper_id": doc.metadata.get("paper_id", ""),
                "chunk_id": doc.metadata.get("chunk_id", doc.id),
                "title": doc.metadata.get("section_title", ""),
                "page": doc.metadata.get("source_page"),
                "section": doc.metadata.get("section_title", ""),
                "anchor_id": doc.metadata.get("anchor_id", ""),
                "chunk_index": doc.metadata.get("chunk_index"),
            }
            for doc in fused
        ]

    def _build_context(self, retrieval_results: list[dict]) -> str:
        if not retrieval_results:
            return ""

        budget = TokenBudget()
        context_parts: list[str] = []

        for idx, doc in enumerate(retrieval_results, 1):
            content = doc.get("content", "")
            if not content:
                continue
            if not budget.can_fit(content):
                break
            budget.allocate(content)
            context_parts.append(f"[{idx}] {content}")

        return "\n\n---\n\n".join(context_parts)

    def _build_messages(self, snapshot: Any, context: str) -> list[dict]:
        """使用快照中冻结的历史，不再读取 live window_store"""
        system_parts = [
            _RAG_SYSTEM_PROMPT.format(context=context) if context else _NO_RAG_SYSTEM_PROMPT
        ]
        if snapshot.history_summary:
            system_parts.append(f"历史摘要：\n{snapshot.history_summary}")
        messages: list[dict] = [{"role": "system", "content": "\n\n".join(system_parts)}]

        for msg in snapshot.recent_window[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": snapshot.prompt})
        return messages

    async def _persist(
        self,
        snapshot: Any,
        full_text: str,
        blocks: list,
        sources: list,
        compacted: bool = False,
    ) -> None:
        """持久化会话，失败不影响 SSE 输出（降级记录日志）"""
        summary = (snapshot.history_summary or "").strip()
        summary_saved = False
        if summary:
            try:
                await self._persistence.save_summary(snapshot.session_id, summary)
                summary_saved = True
            except Exception:
                logger.warning("summary persist failed for session %s", snapshot.session_id, exc_info=True)

        if compacted and summary_saved:
            try:
                await self._window_store.clear(snapshot.session_id)
            except Exception:
                logger.warning("window_store compact failed for session %s", snapshot.session_id, exc_info=True)

        if not full_text:
            return

        blocks_json = json.dumps(
            [b.model_dump() if hasattr(b, "model_dump") else b for b in blocks],
            ensure_ascii=False,
        )
        sources_json = json.dumps(
            [s.model_dump() if hasattr(s, "model_dump") else s for s in sources],
            ensure_ascii=False,
        )

        try:
            await self._window_store.add_message(
                snapshot.session_id,
                {"role": "user", "content": snapshot.prompt},
            )
            await self._window_store.add_message(
                snapshot.session_id,
                {"role": "assistant", "content": full_text},
            )
        except Exception:
            logger.warning("window_store persist failed for session %s", snapshot.session_id, exc_info=True)

        try:
            await self._persistence.save_message(
                session_id=snapshot.session_id,
                role="user",
                content=snapshot.prompt,
            )
            await self._persistence.save_message(
                session_id=snapshot.session_id,
                role="assistant",
                content=full_text,
                blocks_json=blocks_json,
                sources_json=sources_json,
            )
        except Exception:
            logger.warning("persistence persist failed for session %s", snapshot.session_id, exc_info=True)
