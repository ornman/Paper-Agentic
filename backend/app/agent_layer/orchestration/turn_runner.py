"""核心编排器：一轮请求的状态机"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from openai import APIConnectionError, APIStatusError, RateLimitError

from app.agent_layer.contracts.query import AskRequest
from app.agent_layer.contracts.sse_events import (
    BlockEvent,
    DoneEvent,
    ErrorEvent,
    ReflectionEvent,
    SourcesEvent,
    ThinkingEvent,
)
from app.agent_layer.hooks.reflection import reflect
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


def _user_friendly_error(exc: Exception) -> str:
    """将内部异常转换为用户友好的错误信息，不暴露内部细节"""
    if isinstance(exc, RateLimitError):
        return "当前请求量较大，请稍后再试"
    if isinstance(exc, APIConnectionError):
        return "无法连接到 AI 服务，请检查网络后重试"
    if isinstance(exc, APIStatusError):
        if exc.status_code >= 500:
            return "AI 服务暂时不可用，请稍后再试"
        return f"请求被拒绝（状态码 {exc.status_code}）"
    if isinstance(exc, TimeoutError):
        return "请求超时，请稍后再试"
    return "处理请求时出现错误，请稍后再试"


_RAG_SYSTEM_PROMPT = """你是一个有帮助的学术写作助手。请用中文回答用户的问题。

你必须基于提供的资料回答。
- 只在有证据时下结论，不要编造来源
- 回答中引用证据时，使用方括号编号，如 [1]、[2]
- 同一个段落可引用多个来源，如 [1][3]
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
        snapshot_builder: Any,
        retrieval_gate: Any,
        source_mapper: Any,
        block_streamer: Any,
        window_store: ConversationWindowStore,
        editor_context_store: EditorContextStore,
        persistence: SessionPersistence,
        vector_store: Any | None = None,
        keyword_search: Any | None = None,
        embedding_client: Any | None = None,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self._chat_model = chat_model
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

    async def run(self, request: AskRequest) -> AsyncIterator[str]:
        request_id = uuid.uuid4().hex

        try:
            if not request.prompt or not request.prompt.strip():
                yield ErrorEvent(message="请提供问题或内容").to_sse_frame()
                return

            snapshot = await self._freeze_snapshot(request, request_id)

            query_text = self._assemble_query(snapshot)

            need_rag = self._retrieval_gate(snapshot)

            if need_rag:
                retrieval_results = await self._retrieve(query_text, snapshot.paper_ids)
                sources = self._source_mapper(retrieval_results)
            else:
                retrieval_results = []
                sources = []

            context = self._build_context(retrieval_results)

            messages = self._build_messages(snapshot, context)

            if snapshot.thinking_enabled:
                yield ThinkingEvent(text="", time_ms=0).to_sse_frame()

            full_text = ""
            model_override = snapshot.model_name or None
            async for chunk in self._chat_model.chat_stream(messages, model=model_override):
                full_text += chunk

            # ── Reflection 循环（独立 hook，不与 compact 耦合）─────
            if snapshot.reflection_enabled:
                ref_result = await reflect(
                    chat_model=self._chat_model,
                    original_query=query_text,
                    llm_output=full_text,
                    context=context,
                )
                for entry in ref_result.feedback_log:
                    yield ReflectionEvent(
                        round=entry["round"],
                        verdict=entry["verdict"],
                        reason=entry["reason"],
                    ).to_sse_frame()
                full_text = ref_result.output

            blocks = self._block_streamer(full_text, sources)
            for block in blocks:
                yield BlockEvent(data=block).to_sse_frame()

            yield SourcesEvent(data=sources).to_sse_frame()

            await self._persist(snapshot, full_text, blocks, sources)

            yield DoneEvent().to_sse_frame()

        except Exception as exc:
            logger.exception("Turn execution failed: %s", exc)
            yield ErrorEvent(message=_user_friendly_error(exc)).to_sse_frame()

    async def _freeze_snapshot(self, request: AskRequest, request_id: str) -> Any:
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

    async def _retrieve(self, query_text: str, paper_ids: list[str] | None) -> list[dict]:
        results: list[dict] = []

        if self._embedding_client is not None and self._vector_store is not None:
            try:
                query_vector = await self._embedding_client.embed_single(query_text)
                dense_results = self._vector_store.query(query_vector, topk=20, paper_ids=paper_ids)
                results.extend(dense_results)
            except Exception as exc:
                logger.warning("Dense retrieval failed: %s", exc)

        if self._keyword_search is not None:
            try:
                sparse_results = self._keyword_search.query(query_text, topk=20, paper_ids=paper_ids)
                results.extend(sparse_results)
            except Exception as exc:
                logger.warning("Keyword retrieval failed: %s", exc)

        return results

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
        system_msg = _RAG_SYSTEM_PROMPT.format(context=context) if context else _NO_RAG_SYSTEM_PROMPT
        messages: list[dict] = [{"role": "system", "content": system_msg}]

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
    ) -> None:
        """持久化会话，失败不影响 SSE 输出（降级记录日志）"""
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
