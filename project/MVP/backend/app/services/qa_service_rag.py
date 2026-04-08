# 问答服务（带 RAG + Query 改写）
# 集成检索增强生成，支持 query 改写后多路检索
from typing import AsyncGenerator, Optional, List
from app.clients.llm_client import LLMClient
from app.repositories import sqlite_repo
from app.services.retrieval_service import retrieve
from app.models.query import QueryContext, SourceItem
import json

# RAG Prompt 模板
_PROMPT_WITH_CONTEXT = """\
你是一个学术写作助手，帮助用户完成论文写作。

以下是从文献库检索到的相关内容：
{retrieved_context}

请基于上述文献内容回答用户问题。
- 回答时请引用来源，格式为 [1]、[2] 等
- 如果检索内容不足以回答，请明确说明
- 不要编造文献中没有的内容

用户问题：{query}
"""


def _build_messages(
    session_id: str,
    query: str,
    context: Optional[QueryContext],
    sources: List[SourceItem],
) -> list[dict]:
    """构建消息列表（含历史和 RAG 上下文）"""
    messages = []

    # 系统提示
    messages.append({
        "role": "system",
        "content": "你是一个专业的学术写作助手，善于分析文献、辅助论文写作。"
    })

    # 历史消息（最近 10 轮）
    history = sqlite_repo.get_messages(session_id)
    recent = history[-20:]
    for msg in recent:
        messages.append({"role": msg.role, "content": msg.content})

    # 当前用户消息（含 RAG 上下文）
    if sources:
        ctx_text = "\n\n".join(
            f"[{s.id}] 来源：{s.document}（第 {s.page} 页）\n{s.content}"
            for s in sources
        )
        user_content = _PROMPT_WITH_CONTEXT.format(
            retrieved_context=ctx_text,
            query=query,
        )
    else:
        # 无检索结果，回退到基础问答
        user_content = f"请回答以下问题：{query}"

    messages.append({"role": "user", "content": user_content})
    return messages


async def ask_stream_with_rag(
    session_id: str,
    query: str,
    context: Optional[QueryContext] = None,
    use_rag: bool = True,
) -> AsyncGenerator[dict, None]:
    """
    流式问答（带 RAG + Query 改写）

    流程：
    1. Query 改写 → 多路检索 → RRF → Rerank
    2. 构建带检索结果的 Prompt
    3. LLM 流式生成

    Yields:
        {"type": "chunk", "data": {"content": str, "index": int}}
        {"type": "sources", "data": {"sources": [...]}}
        {"type": "rewrite", "data": {"original": str, "rewritten": [str, ...]}}
        {"type": "done", "data": {"total_tokens": int}}
    """
    sources = []
    rewritten_queries = [query]

    # 1. RAG 检索（含 query 改写）
    # 这里必须允许回退到纯问答。
    # 原因是插件当前首要目标是“能真实对话”，
    # 不能因为索引维度污染、检索服务异常等外围问题把整条对话链路打死。
    if use_rag:
        try:
            retrieval_result = await retrieve(query, context=context, top_k=10)
            rewritten_queries = retrieval_result["rewritten_queries"]

            sources = [
                SourceItem(
                    id=i + 1,
                    content=r["content"],
                    document=r["document"],
                    page=r["page"],
                    score=r["score"],
                )
                for i, r in enumerate(retrieval_result["results"])
            ]
        except Exception as retrieval_error:
            print(f"⚠️ RAG 检索失败，回退到纯问答：{retrieval_error}")
            sources = []
            rewritten_queries = [query]

    # 2. 发送改写信息（让前端知道查了什么）
    if rewritten_queries != [query]:
        yield {
            "type": "rewrite",
            "data": {
                "original": query,
                "rewritten": rewritten_queries,
            }
        }

    # 3. 发送引用来源
    if sources:
        yield {
            "type": "sources",
            "data": {"sources": [s.model_dump() for s in sources]}
        }

    # 4. 构建消息
    messages = _build_messages(session_id, query, context, sources)

    # 5. 流式生成
    llm = LLMClient()
    full_response = []
    index = 0

    async for chunk in llm.chat_stream(messages):
        full_response.append(chunk)
        yield {"type": "chunk", "data": {"content": chunk, "index": index}}
        index += 1

    # 6. 保存消息
    assistant_content = "".join(full_response)
    sqlite_repo.add_message(session_id, "user", query)
    sqlite_repo.add_message(
        session_id,
        "assistant",
        assistant_content,
        sources=[s.model_dump() for s in sources] if sources else None,
    )

    yield {"type": "done", "data": {"total_tokens": 0}}
