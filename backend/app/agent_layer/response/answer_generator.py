"""回答生成器"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from pathlib import Path

from app.agent_layer.planning.input_assembler import build_source_label, truncate_snippet
from app.agent_layer.runtime.chat_model import ChatModel
from app.data_layer.contracts.conversation import ConversationMessage
from app.data_layer.retrieval import fusion
from app.data_layer.data_persistence.chroma_store.keyword_index import KeywordIndex
from app.data_layer.data_persistence.chroma_store.vector_index import VectorIndex
from app.service_layer.config.settings import BackendSettings

logger = logging.getLogger("paper-assistant")

_SYSTEM_PROMPT = """你是一个有帮助的助手。请用中文回答用户的问题。

你必须基于提供的资料回答。
- 只在有证据时下结论，不要编造来源
- 回答中引用证据时，使用方括号编号，如 [1]、[2]
- 同一个段落可引用多个来源，如 [1][3]
- 编号必须对应提供给你的来源顺序
- 优先把结论写清楚，再用编号引用支撑，不要输出文件 hash 或内部 ID

{context}
"""

_MAX_CONTEXT_TOKENS = 30000


class AnswerGenerator:
    def __init__(
        self,
        settings: BackendSettings,
        chat_model: ChatModel,
        vector_store: VectorIndex,
        keyword_search: KeywordIndex,
        conversation_repo: object,
        embedding_client: object | None = None,
    ):
        self._settings = settings
        self._chat_model = chat_model
        self._vector_store = vector_store
        self._keyword_search = keyword_search
        self._conversation_repo = conversation_repo
        self._embedding_client = embedding_client

    async def generate(
        self,
        session_id: str,
        query_text: str,
        paper_ids: list[str] | None = None,
    ) -> AsyncIterator[dict]:
        """流式回答，yield SSE 事件"""
        if not query_text:
            yield {"event": "error", "data": {"message": "请提供问题或内容"}}
            return

        # 1. Dense 检索
        query_vector: list[float] = []
        if self._embedding_client is not None:
            try:
                query_vector = await self._embedding_client.embed_single(query_text)
            except Exception as e:
                logger.warning("Embedding 生成失败，跳过 dense 检索: %s", e)

        # 2. BM25 检索 + RRF 融合
        dense_results = self._vector_store.query(query_vector, topk=20, paper_ids=paper_ids) if query_vector else []
        sparse_results = self._keyword_search.query(query_text, topk=20, paper_ids=paper_ids)
        results = fusion.rrf_fuse(dense_results, sparse_results, topk=10, keyword_index=self._keyword_search)

        if not results:
            yield {
                "event": "metadata",
                "data": {"session_id": session_id, "source_count": 0, "sources": []},
            }
            yield {"event": "chunk", "data": {"content": "未找到相关文献，无法基于文献内容回答该问题。请确认已导入相关文献，或尝试调整问题描述。"}}
            yield {"event": "done", "data": {}}
            return

        # 3. 拼装上下文
        context_parts: list[str] = []
        sources: list[dict] = []
        total_tokens = 0

        for doc in results:
            # 兼容 Doc.fields 和 FusedDoc.metadata
            if hasattr(doc, "fields") and isinstance(doc.fields, dict):
                fields = doc.fields
            elif hasattr(doc, "metadata") and isinstance(doc.metadata, dict):
                fields = doc.metadata
            else:
                fields = {}
            content = fields.get("content", "") if fields else ""
            if not content:
                content = getattr(doc, "content", "")

            tokens = _estimate_tokens(content)
            if total_tokens + tokens > _MAX_CONTEXT_TOKENS:
                break

            pid = fields.get("paper_id", "") if fields else ""
            page = fields.get("source_page", 0) if fields else 0
            section = fields.get("section_title", "") if fields else ""
            title = "未命名论文"
            snippet = truncate_snippet(content)
            label = build_source_label(title, page if isinstance(page, int) else None, section)
            source_info = {
                "id": fields.get("anchor_id", f"{pid}_{fields.get('chunk_index', '')}"),
                "paper_id": pid,
                "title": title,
                "page": page,
                "section": section,
                "content": snippet,
                "citation_label": label,
            }
            sources.append(source_info)
            context_parts.append(f"[{len(sources)}] {label}\n摘录：{snippet}")
            total_tokens += tokens

        context = "\n\n---\n\n".join(context_parts)

        # 4. 构建消息
        system_msg = _SYSTEM_PROMPT.format(context=context)
        messages = [{"role": "system", "content": system_msg}]

        # 加载对话历史
        try:
            history = self._conversation_repo.get_messages(session_id, limit=20)
            for msg in history[-10:]:
                messages.append({"role": msg.role, "content": msg.content})
        except Exception:
            pass

        messages.append({"role": "user", "content": query_text})

        # 5. 发送 metadata + 流式 chunk
        yield {
            "event": "metadata",
            "data": {
                "session_id": session_id,
                "source_count": len(sources),
                "sources": sources,
            },
        }

        full_response: list[str] = []
        try:
            async for chunk in self._chat_model.chat_stream(messages):
                full_response.append(chunk)
                yield {"event": "chunk", "data": {"content": chunk}}
        except Exception as e:
            logger.error("LLM 流式调用失败: %s", e)
            yield {"event": "error", "data": {"message": "LLM 服务暂时不可用"}}

        # 6. 保存对话历史
        if full_response:
            from app.data_layer.contracts.library_item import utc_now_iso
            now = utc_now_iso()
            try:
                self._conversation_repo.save_message(
                    ConversationMessage(session_id=session_id, role="user", content=query_text, created_at=now)
                )
                self._conversation_repo.save_message(
                    ConversationMessage(session_id=session_id, role="assistant", content="".join(full_response), created_at=now)
                )
            except Exception as e:
                logger.warning("保存对话失败: %s", e)

        yield {"event": "done", "data": {}}

    async def generate_title(self, first_message: str) -> str:
        """根据首条用户消息生成简短对话标题"""
        from app.agent_layer.planning.input_assembler import sanitize_title
        prompt = (
            "请根据以下用户消息，生成一个简短的对话标题（5-12个汉字）。\n"
            "要求：只输出标题本身，不要解释，不要换行，不要加引号或标点。\n\n"
            f"用户消息：{first_message[:200]}\n\n标题："
        )
        fallback = first_message[:20]
        response = await self._chat_model.chat([{"role": "user", "content": prompt}])
        return sanitize_title(response, fallback)


def _estimate_tokens(text: str) -> int:
    count = 0.0
    for ch in text:
        count += 1.5 if "一" <= ch <= "鿿" else 0.75
    return int(count)
