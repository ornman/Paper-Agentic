# 问答服务
# 封装 LLM 调用、上下文管理、流式输出
# 优先级最高：先跑通基础问答，不依赖 RAG
from typing import AsyncGenerator, Optional
from app.clients.llm_client import LLMClient
from app.repositories import sqlite_repo
from app.models.query import QueryContext, SourceItem
import json

# Prompt 模板：4 种场景
# 场景1: 只有 query（最基础）
_PROMPT_QUERY_ONLY = """\
你是一个学术写作助手，帮助用户完成论文写作。
请根据用户的问题，给出详细、准确的回答。
如果无法回答，请直接说明原因，不要编造内容。

用户问题：{query}
"""

# 场景2: query + 已写内容
_PROMPT_WITH_WRITTEN = """\
你是一个学术写作助手，帮助用户完成论文写作。

用户当前已写内容：
{written_content}

请根据已写内容和用户的问题，给出有针对性的回答。
如果无法回答，请直接说明原因，不要编造内容。

用户问题：{query}
"""

# 场景3: query + 已写内容 + 圈选文本
_PROMPT_WITH_SELECTED = """\
你是一个学术写作助手，帮助用户完成论文写作。

用户当前已写内容：
{written_content}

用户圈选的文本（重点关注）：
{selected_text}

请结合圈选文本和已写内容，回答用户的问题。
如果无法回答，请直接说明原因，不要编造内容。

用户问题：{query}
"""

# 场景4: query + RAG 检索结果（后续启用）
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


def _build_prompt(query: str, context: Optional[QueryContext], sources: list[SourceItem]) -> str:
    """
    根据输入场景选择对应的 Prompt 模板

    优先级：RAG 上下文 > 圈选文本 > 已写内容 > 纯问题
    """
    if sources:
        # 有 RAG 检索结果
        ctx_text = "\n\n".join(
            f"[{s.id}] 来源：{s.document}（第 {s.page} 页）\n{s.content}"
            for s in sources
        )
        return _PROMPT_WITH_CONTEXT.format(retrieved_context=ctx_text, query=query)

    if context is None:
        return _PROMPT_QUERY_ONLY.format(query=query)

    if context.selected_text and context.written_content:
        return _PROMPT_WITH_SELECTED.format(
            written_content=context.written_content,
            selected_text=context.selected_text,
            query=query,
        )

    if context.written_content:
        return _PROMPT_WITH_WRITTEN.format(
            written_content=context.written_content,
            query=query,
        )

    return _PROMPT_QUERY_ONLY.format(query=query)


def _build_messages(session_id: str, query: str, context: Optional[QueryContext], sources: list[SourceItem]) -> list[dict]:
    """
    构建完整的消息列表（含历史对话）
    """
    messages = []

    # 系统提示
    messages.append({
        "role": "system",
        "content": "你是一个专业的学术写作助手，善于分析文献、辅助论文写作。"
    })

    # 历史消息（最近 10 轮，避免上下文过长）
    history = sqlite_repo.get_messages(session_id)
    recent = history[-20:]  # 最近 20 条（10 轮对话）
    for msg in recent:
        messages.append({"role": msg.role, "content": msg.content})

    # 当前用户消息（含 Prompt 模板）
    user_content = _build_prompt(query, context, sources)
    messages.append({"role": "user", "content": user_content})

    return messages


async def ask_stream(
    session_id: str,
    query: str,
    context: Optional[QueryContext] = None,
    sources: Optional[list[SourceItem]] = None,
) -> AsyncGenerator[dict, None]:
    """
    流式问答，产生 SSE 事件字典

    Yields:
        {"type": "chunk", "data": {"content": str, "index": int}}
        {"type": "sources", "data": {"sources": [...]}}
        {"type": "done", "data": {"total_tokens": int}}
    """
    sources = sources or []
    messages = _build_messages(session_id, query, context, sources)

    # 先发送引用来源
    if sources:
        yield {
            "type": "sources",
            "data": {"sources": [s.model_dump() for s in sources]}
        }

    # 流式生成回答
    llm = LLMClient()
    full_response = []
    index = 0

    async for chunk in llm.chat_stream(messages):
        full_response.append(chunk)
        yield {"type": "chunk", "data": {"content": chunk, "index": index}}
        index += 1

    # 保存消息到数据库
    assistant_content = "".join(full_response)
    sqlite_repo.add_message(session_id, "user", query)
    sqlite_repo.add_message(
        session_id,
        "assistant",
        assistant_content,
        sources=[s.model_dump() for s in sources] if sources else None,
    )

    yield {"type": "done", "data": {"total_tokens": 0}}


def get_history(session_id: str) -> list[dict]:
    """获取会话历史"""
    messages = sqlite_repo.get_messages(session_id)
    return [
        {
            "id": m.id,
            "session_id": m.session_id,
            "role": m.role,
            "content": m.content,
            "sources": json.loads(m.sources) if m.sources else None,
            "created_at": m.created_at,
        }
        for m in messages
    ]


def clear_history(session_id: str) -> int:
    """清空会话历史，返回删除数量"""
    return sqlite_repo.clear_messages(session_id)
