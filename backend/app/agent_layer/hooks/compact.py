"""上下文压缩"""

from __future__ import annotations

import logging

from app.agent_layer.runtime.chat_model import ChatModel

logger = logging.getLogger("paper-assistant")


async def compact_conversation(
    chat_model: ChatModel,
    messages: list[dict],
    max_summary_tokens: int = 500,
) -> str:
    """使用小模型总结历史对话"""
    if not messages:
        return ""

    # 构建总结提示
    history_text = "\n".join([f"{msg.get('role', 'user')}: {msg.get('content', '')}" for msg in messages])
    prompt = (
        f"请总结以下对话历史，保留关键信息和上下文，控制在 {max_summary_tokens} 个 token 以内。\n\n"
        f"对话历史：\n{history_text}\n\n总结："
    )

    try:
        summary = await chat_model.chat([{"role": "user", "content": prompt}])
        logger.info("对话压缩完成，摘要长度: %d", len(summary))
        return summary
    except Exception as e:
        logger.error("对话压缩失败: %s", e)
        return ""
