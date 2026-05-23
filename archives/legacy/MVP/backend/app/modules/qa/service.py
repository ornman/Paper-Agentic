# 问答服务（新架构）
# 集成 RAG + Query 改写 + 流式输出

from __future__ import annotations

from typing import AsyncGenerator

from app.clients.kimi_client import KimiLLMClient, Message
from app.clients.vlm_client import LLMClient
from app.core.retry import retry_async
from app.modules.retrieval.service import RetrievalService
from app.repositories.sqlite_repo import add_message, get_messages
from app.services.query_rewrite_service import QueryRewriteService

# RAG Prompt 模板
_PROMPT_WITH_CONTEXT = """你是一个学术写作助手，帮助用户完成论文写作。

以下是从文献库检索到的相关内容：
{retrieved_context}

请基于上述文献内容回答用户问题。
- 回答时请引用来源，格式为 [来源:论文名 页码X]
- 如果检索内容不足以回答，请明确说明
- 不要编造文献中没有的内容

用户问题：{query}"""


def _build_messages(
    session_id: str,
    query: str,
    sources: list[dict],
) -> list[Message]:
    """构建消息列表（含历史和 RAG 上下文）."""
    messages = [
        Message(
            role="system",
            content="你是一个专业的学术写作助手，善于分析文献、辅助论文写作。",
        )
    ]

    # 历史消息（最近 10 轮）
    history = get_messages(session_id)
    recent = history[-20:] if len(history) > 20 else history
    for msg in recent:
        messages.append(Message(role=msg.role, content=msg.content))

    # 当前用户消息（含 RAG 上下文）
    if sources:
        ctx_text = "\n\n".join(
            f"[来源:{s['payload'].get('paper', 'unknown')} 页码{s['payload'].get('page', '?')}]\n{s['payload'].get('content', '')}"
            for s in sources
        )
        user_content = _PROMPT_WITH_CONTEXT.format(
            retrieved_context=ctx_text,
            query=query,
        )
    else:
        user_content = f"请回答以下问题：{query}"

    messages.append(Message(role="user", content=user_content))
    return messages


class QAService:
    """问答服务."""

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        retrieval_service: RetrievalService | None = None,
        query_rewrite_service: QueryRewriteService | None = None,
    ) -> None:
        self.llm_client = llm_client or KimiLLMClient()
        self.retrieval_service = retrieval_service or RetrievalService()
        self.query_rewrite_service = query_rewrite_service or QueryRewriteService()

    async def ask_stream_with_rag(
        self,
        session_id: str,
        query: str,
        use_rag: bool = True,
        resource_types: list[str] | None = None,
        selected_papers: list[str] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """流式问答（带 RAG + Query 改写）.

        Args:
            session_id: 会话 ID
            query: 用户问题
            use_rag: 是否使用 RAG
            resource_types: 资源类型过滤（未来扩展）
            selected_papers: 用户选择的论文 ID（未来扩展）

        Yields:
            {"type": "chunk", "data": {"content": str, "index": int}}
            {"type": "sources", "data": {"sources": [...]}}
            {"type": "rewrite", "data": {"original": str, "rewritten": [str, ...]}}
            {"type": "done", "data": {"total_tokens": int}}

        ═════════════════════════════════════════════════════════════════════
        🔮 未来扩展：用户自选文献功能
        ═════════════════════════════════════════════════════════════════════

        前端交互流程：
        1. 用户提问前，展示文献列表（论文、笔记、视频等）
        2. 用户勾选要参考的文献
        3. 前端传递 selected_papers = ["paper_abc", "note_xyz"]
        4. 后端只在选中的范围内检索

        产品价值：
        - 提高准确性：用户知道答案在哪些文献里
        - 增强掌控感：用户主动选择，而非被动接受
        - 减少干扰：排除不相关的文献
        - 提升黏性：用户参与决策过程
        """
        sources = []
        rewritten_queries = [query]

        # 1. Query 改写
        try:
            rewritten_queries = await self.query_rewrite_service.rewrite(query)
        except Exception as e:
            print(f"⚠️ Query 改写失败：{e}")
            rewritten_queries = [query]

        # 2. 发送改写信息
        if rewritten_queries != [query]:
            yield {
                "type": "rewrite",
                "data": {
                    "original": query,
                    "rewritten": rewritten_queries,
                },
            }

        # 3. RAG 检索
        if use_rag:
            try:
                retrieval_result = await self.retrieval_service.retrieve(
                    rewritten_queries[0],
                    top_k=10,
                    resource_types=resource_types,
                    selected_papers=selected_papers,
                )
                sources = retrieval_result["results"]
            except Exception as e:
                print(f"⚠️ RAG 检索失败，回退到纯问答：{e}")
                sources = []

        # 4. 发送引用来源
        if sources:
            yield {
                "type": "sources",
                "data": {"sources": sources},
            }

        # 5. 构建消息
        messages = _build_messages(session_id, query, sources)

        # 6. 流式生成（带重试）
        full_response = []
        index = 0

        try:
            async for chunk in await retry_async(self.llm_client.chat_stream)(messages):
                full_response.append(chunk)
                yield {"type": "chunk", "data": {"content": chunk, "index": index}}
                index += 1
        except Exception as e:
            print(f"⚠️ LLM 流式生成失败: {e}")
            # 降级：返回错误消息
            yield {"type": "error", "data": {"message": f"LLM 生成失败: {str(e)}"}}
            return

        # 7. 保存消息
        assistant_content = "".join(full_response)
        add_message(session_id, "user", query)
        add_message(
            session_id,
            "assistant",
            assistant_content,
            sources=sources if sources else None,
        )

        yield {"type": "done", "data": {"total_tokens": len(assistant_content)}}
