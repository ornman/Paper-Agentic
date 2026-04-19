"""RAG 问答服务（P3 简化版：单路 dense 检索 + LLM 流式）"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from app.api.v1.deps import get_redis, get_zvec
from app.clients.embedding_client import EmbeddingClient
from app.clients.llm_client import LLMClient

logger = logging.getLogger("paper-assistant")

_SYSTEM_PROMPT = """你是一个学术论文研究助手。你的职责是：
1. 基于提供的参考文献片段，准确回答用户关于论文内容的问题
2. 回答时引用来源（标注论文标题和页码）
3. 如果参考内容不足以回答问题，坦诚说明
4. 使用中文回答

参考文献片段：
{context}"""

_MAX_CONTEXT_TOKENS = 30000


class QAService:
    def __init__(self):
        self._llm = LLMClient()
        self._embedding = EmbeddingClient()

    async def query(
        self,
        session_id: str,
        prompt: str,
        selection: str = "",
        draft: str = "",
        paper_ids: list[str] | None = None,
    ) -> AsyncIterator[dict]:
        """流式问答，yield SSE 事件"""
        # 1. 构建查询
        query_text = prompt
        if selection:
            query_text = f"{prompt}\n\n用户圈选的文本：{selection}" if prompt else selection
        if draft:
            query_text = f"{query_text}\n\n用户已写内容：{draft}" if query_text else draft

        if not query_text:
            yield {"event": "error", "data": {"message": "请提供问题或内容"}}
            return

        # 2. Embedding
        query_vec = await self._embedding.embed_single(query_text)

        # 3. Zvec 检索
        zvec = get_zvec()
        results = zvec.query(query_vec, topk=10)

        if not results:
            yield {
                "event": "metadata",
                "data": {"session_id": session_id, "source_count": 0, "sources": []},
            }
            async for chunk in self._llm.chat_stream(
                [{"role": "user", "content": query_text}]
            ):
                yield {"event": "chunk", "data": {"content": chunk}}
            yield {"event": "done", "data": {}}
            return

        # 4. 拼装上下文
        context_parts: list[str] = []
        sources: list[dict] = []
        total_tokens = 0

        for doc in results:
            fields = doc.fields if hasattr(doc, "fields") else {}
            content = fields.get("content", "") if isinstance(fields, dict) else ""
            if not content:
                content = getattr(doc, "content", "")

            tokens = len(content)  # 粗略估算
            if total_tokens + tokens > _MAX_CONTEXT_TOKENS:
                break

            source_info = {
                "paper_id": fields.get("paper_id", "") if isinstance(fields, dict) else "",
                "page": fields.get("source_page", 0) if isinstance(fields, dict) else 0,
                "section": fields.get("section_title", "") if isinstance(fields, dict) else "",
            }
            sources.append(source_info)
            context_parts.append(f"[来源: 论文 {source_info['paper_id'][:8]}, 第{source_info['page']}页]\n{content}")
            total_tokens += tokens

        context = "\n\n---\n\n".join(context_parts)

        # 5. 构建消息
        system_msg = _SYSTEM_PROMPT.format(context=context)
        messages = [{"role": "system", "content": system_msg}]

        # 加载对话历史
        redis = get_redis()
        try:
            history = await redis.get_messages(session_id, limit=20)
            for msg in history[-10:]:  # 最近 10 条
                if msg.get("role") in ("user", "assistant"):
                    messages.append({"role": msg["role"], "content": msg["content"]})
        except Exception:
            pass  # Redis 不可用时跳过历史

        messages.append({"role": "user", "content": query_text})

        # 6. 发送 metadata + 流式 chunk
        yield {
            "event": "metadata",
            "data": {
                "session_id": session_id,
                "source_count": len(sources),
                "sources": sources,
            },
        }

        full_response: list[str] = []
        async for chunk in self._llm.chat_stream(messages):
            full_response.append(chunk)
            yield {"event": "chunk", "data": {"content": chunk}}

        # 7. 保存对话历史
        try:
            await redis.add_message(session_id, {"role": "user", "content": query_text})
            await redis.add_message(session_id, {"role": "assistant", "content": "".join(full_response)})
        except Exception:
            pass

        yield {"event": "done", "data": {}}

    async def close(self) -> None:
        await self._llm.close()
        await self._embedding.close()
