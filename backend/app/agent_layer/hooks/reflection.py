"""Reflection 循环：LLM 自检 + 定向重生成

独立 hook，不与 compact 耦合。
最多 3 轮、2 次方向切换，"supported" 就停。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("paper-assistant")

_REFLECTION_PROMPT = """你是一个学术回答质量审查员。请判断以下回答是否被提供的资料充分支持。

用户提问：{query}

{context_section}

LLM 回答：
{llm_output}

请严格按以下 JSON 格式回复，不要添加其他内容：
{{"verdict": "supported" 或 "unsupported", "reason": "简要原因", "direction": "refine" 或 "rephrase"}}"""

_CONTEXT_SECTION = """参考资料：
{context}"""

_NO_CONTEXT_SECTION = "（无外部资料，基于常识回答）"

_EVIDENCE_JUDGE_PROMPT = """你是一个学术证据审查员。请判断以下资料是否足以回答用户的问题。

用户提问：{query}

检索到的资料：
{evidence}

请严格按以下 JSON 格式回复，不要添加其他内容：
{{"verdict": "supported" 或 "insufficient" 或 "conflicting" 或 "off_track", "reason": "简要原因"}}
说明：
- supported：资料充分支持回答
- insufficient：资料不足，需要继续检索
- conflicting：检索到的资料互相矛盾，需要换关键词或换焦点再验证
- off_track：检索方向偏离问题，需要换方向"""

_MAX_ROUNDS = 3
_MAX_SWITCHES = 2


@dataclass(frozen=True)
class ReflectionResult:
    output: str
    rounds_used: int
    direction_switches: int
    feedback_log: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class EvidenceJudgment:
    verdict: str  # "supported" | "insufficient" | "conflicting" | "off_track"
    reason: str


def _parse_verdict(raw: str) -> tuple[str, str, str]:
    """解析 reflection 响应，返回 (verdict, reason, direction)"""
    import json

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(cleaned)
        verdict = str(data.get("verdict", "unsupported")).lower()
        reason = str(data.get("reason", ""))
        direction = str(data.get("direction", "refine")).lower()
        if verdict not in ("supported", "unsupported"):
            verdict = "unsupported"
        if direction not in ("refine", "rephrase"):
            direction = "refine"
        return verdict, reason, direction
    except (json.JSONDecodeError, ValueError):
        if "supported" in cleaned.lower() and "unsupported" not in cleaned.lower():
            return "supported", cleaned, "refine"
        return "unsupported", cleaned, "refine"


async def judge_evidence(
    chat_model: Any,
    query: str,
    context: str,
    *,
    judge_model: Any | None = None,
) -> EvidenceJudgment:
    """判断检索到的证据是否足以回答查询。

    Args:
        chat_model: LLM 客户端
        query: 用户查询
        evidence: 检索到的证据文本

    Returns:
        EvidenceJudgment 包含 verdict 和 reason
    """
    if not context:
        return EvidenceJudgment(verdict="insufficient", reason="无检索结果")

    model = judge_model if judge_model is not None else chat_model
    prompt = _EVIDENCE_JUDGE_PROMPT.format(query=query, evidence=context)
    try:
        raw = await model.chat([{"role": "user", "content": prompt}])
    except Exception as exc:
        logger.warning("Evidence judgment failed: %s", exc)
        return EvidenceJudgment(verdict="supported", reason="判断失败，默认通过")

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    import json as _json
    try:
        data = _json.loads(cleaned)
        verdict = str(data.get("verdict", "supported")).lower()
        reason = str(data.get("reason", ""))
        if verdict not in ("supported", "insufficient", "conflicting", "off_track"):
            verdict = "supported"
        return EvidenceJudgment(verdict=verdict, reason=reason)
    except (_json.JSONDecodeError, ValueError):
        return EvidenceJudgment(verdict="supported", reason="解析失败，默认通过")


async def reflect(
    chat_model: Any,
    original_query: str,
    llm_output: str,
    context: str = "",
    max_rounds: int = _MAX_ROUNDS,
    *,
    reflection_model: Any | None = None,
) -> ReflectionResult:
    """对 LLM 输出执行 reflection 循环。

    Args:
        chat_model: LLM 客户端
        original_query: 用户原始查询
        llm_output: LLM 生成的回答
        context: RAG 检索到的上下文（可为空）
        max_rounds: 最大 reflection 轮数（默认 3）

    Returns:
        ReflectionResult 包含最终输出、轮数、方向切换次数、反馈日志
    """
    current_output = llm_output
    feedback_log: list[dict] = []
    last_direction: str | None = None
    direction_switches = 0
    model = reflection_model if reflection_model is not None else chat_model

    for round_num in range(1, max_rounds + 1):
        context_section = (
            _CONTEXT_SECTION.format(context=context)
            if context
            else _NO_CONTEXT_SECTION
        )
        prompt = _REFLECTION_PROMPT.format(
            query=original_query,
            context_section=context_section,
            llm_output=current_output,
        )

        try:
            raw_response = await model.chat([{"role": "user", "content": prompt}])
        except Exception as exc:
            logger.warning("Reflection round %d failed: %s", round_num, exc)
            break

        verdict, reason, direction = _parse_verdict(raw_response)

        feedback_log.append({
            "round": round_num,
            "verdict": verdict,
            "reason": reason,
            "direction": direction,
        })

        logger.info(
            "Reflection round %d/%d: verdict=%s, direction=%s",
            round_num,
            max_rounds,
            verdict,
            direction,
        )

        if verdict == "supported":
            break

        if last_direction is not None and direction != last_direction:
            direction_switches += 1
            if direction_switches >= _MAX_SWITCHES:
                logger.info(
                    "Reflection: hit max direction switches (%d), stopping",
                    direction_switches,
                )
                break

        last_direction = direction

        refine_prompt = (
            f"请改进以下回答，使其更好地被资料支持。\n\n"
            f"用户提问：{original_query}\n\n"
            f"当前回答：\n{current_output}\n\n"
            f"改进方向：{reason}\n\n"
            f"改进后的回答："
        )

        try:
            current_output = await model.chat(
                [{"role": "user", "content": refine_prompt}]
            )
        except Exception as exc:
            logger.warning("Refinement round %d failed: %s", round_num, exc)
            break

    return ReflectionResult(
        output=current_output,
        rounds_used=len(feedback_log),
        direction_switches=direction_switches,
        feedback_log=feedback_log,
    )
