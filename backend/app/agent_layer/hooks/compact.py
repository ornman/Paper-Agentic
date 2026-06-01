"""上下文压缩

两种受众：
1. 用户侧：通过 MetadataEvent.degraded_flags 感知压缩状态
2. 开发者侧：日志记录压缩耗时、降级原因

降级策略（不丢失上下文）：
1. 正常：LLM 总结 → 返回摘要
2. 降级 1：LLM 失败 → 保留最近 N 条消息 + 截断旧消息
3. 降级 2：空间仍不足 → 清空 history_summary，仅保留 recent_window
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.agent_layer.runtime.chat_model import ChatModel
from app.agent_layer.runtime.token_budget import estimate_tokens

logger = logging.getLogger("paper-assistant")


@dataclass
class CompactResult:
    """压缩结果"""
    summary: str
    degraded: bool = False
    degrade_reason: str | None = None
    original_count: int = 0
    summary_tokens: int = 0


async def compact_conversation(
    chat_model: ChatModel,
    messages: list[dict],
    max_summary_tokens: int = 0,
    max_context_tokens: int = 0,
) -> CompactResult:
    """压缩对话历史，失败时降级而非丢失上下文

    Args:
        chat_model: LLM 客户端
        messages: 待压缩的历史消息
        max_summary_tokens: 摘要目标 token 数（0 = 从 settings 读取）
        max_context_tokens: 模型最大上下文 token 数（0 = 从 settings 读取）

    Returns:
        CompactResult（summary 可能为空，但不会同时丢失上下文）
    """
    from app.service_layer.config.settings import get_settings
    _s = get_settings()
    if not max_summary_tokens:
        max_summary_tokens = _s.compact_max_summary_tokens
    if not max_context_tokens:
        max_context_tokens = _s.context_window_tokens

    if not messages:
        return CompactResult(summary="", original_count=0)

    original_count = len(messages)

    # ── 尝试 1：LLM 总结 ──
    try:
        history_text = "\n".join(
            [f"{msg.get('role', 'user')}: {msg.get('content', '')}" for msg in messages]
        )
        prompt = (
            f"请总结以下对话历史，保留关键信息和上下文，"
            f"控制在 {max_summary_tokens} 个 token 以内。\n\n"
            f"对话历史：\n{history_text}\n\n总结："
        )
        summary = await chat_model.chat([{"role": "user", "content": prompt}])
        summary = summary.strip()

        if summary:
            summary_tokens = estimate_tokens(summary)
            logger.info(
                "对话压缩完成: %d 条 → ~%d tokens (原始 %d 条)",
                original_count, summary_tokens, original_count,
            )
            return CompactResult(
                summary=summary,
                degraded=False,
                original_count=original_count,
                summary_tokens=summary_tokens,
            )

        logger.warning("LLM 返回空摘要，降级到消息截断")
    except Exception as e:
        logger.warning("LLM 压缩失败: %s，降级到消息截断", e)

    # ── 降级 1：保留最近 N 条消息 ──
    keep_recent = _s.compact_fallback_keep_recent
    kept = messages[-keep_recent:]
    kept_tokens = estimate_tokens(
        "\n".join(m.get("content", "") for m in kept)
    )

    if kept_tokens < max_context_tokens * 0.8:
        fallback_summary = _build_fallback_summary(kept)
        logger.info(
            "降级压缩: %d 条 → 保留最近 %d 条 (~%d tokens)",
            original_count, len(kept), kept_tokens,
        )
        return CompactResult(
            summary=fallback_summary,
            degraded=True,
            degrade_reason="llm_unavailable",
            original_count=original_count,
            summary_tokens=kept_tokens,
        )

    # ── 降级 2：仅保留最近 2 条 ──
    minimal = messages[-2:]
    minimal_summary = _build_fallback_summary(minimal)
    minimal_tokens = estimate_tokens(
        "\n".join(m.get("content", "") for m in minimal)
    )
    logger.warning(
        "深度降级: 仅保留最近 2 条 (~%d tokens)", minimal_tokens,
    )
    return CompactResult(
        summary=minimal_summary,
        degraded=True,
        degrade_reason="context_overflow",
        original_count=original_count,
        summary_tokens=minimal_tokens,
    )


def _build_fallback_summary(messages: list[dict]) -> str:
    """从消息列表构建降级摘要（不依赖 LLM）"""
    parts = []
    for msg in messages:
        role = "用户" if msg.get("role") == "user" else "助手"
        content = msg.get("content", "")
        # 截断过长的消息
        if len(content) > 200:
            content = content[:200] + "…"
        parts.append(f"{role}: {content}")
    return "（压缩降级）最近对话：\n" + "\n".join(parts)
