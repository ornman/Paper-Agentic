"""Tool call 循环：多轮工具调用编排，硬上限 5 轮防无限循环"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger("paper-assistant")

_MAX_TOOL_ROUNDS = 5


class ToolLoopEvent(BaseModel):
    """SSE 事件：工具调用轮次"""
    event: str = "tool_round"
    round: int
    tool_name: str
    status: str  # "calling" | "success" | "error" | "max_rounds"

    def to_sse_frame(self) -> str:
        payload = {
            "round": self.round,
            "tool_name": self.tool_name,
            "status": self.status,
        }
        return f"event: tool_round\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    tool_name: str
    success: bool
    data: Any = None
    error: str = ""


@dataclass
class ToolLoopResult:
    final_output: str
    rounds_used: int
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    hit_max_rounds: bool = False


# 工具函数签名：接收参数字典，返回任意结果
ToolFunc = Callable[[dict[str, Any]], Coroutine[Any, Any, Any]]


class ToolRegistry:
    """工具注册表：名称 → 可调用函数"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolFunc] = {}

    def register(self, name: str, func: ToolFunc) -> None:
        self._tools[name] = func

    def get(self, name: str) -> ToolFunc | None:
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        return name in self._tools

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())


async def execute_tool_loop(
    llm_decide: Callable[[list[dict]], Coroutine[Any, Any, ToolCall | None]],
    initial_messages: list[dict],
    registry: ToolRegistry,
    max_rounds: int = _MAX_TOOL_ROUNDS,
) -> ToolLoopResult:
    """执行多轮工具调用循环。

    Args:
        llm_decide: 接收当前消息列表，返回 ToolCall 或 None（表示结束循环）
        initial_messages: 初始消息列表
        registry: 工具注册表
        max_rounds: 最大轮次（默认 5，硬上限）

    Returns:
        ToolLoopResult 包含最终输出、轮次、调用历史
    """
    messages = list(initial_messages)
    tool_calls: list[ToolCall] = []
    tool_results: list[ToolResult] = []
    rounds_used = 0
    hit_max = False

    for round_num in range(1, max_rounds + 1):
        call = await llm_decide(messages)
        if call is None:
            break

        rounds_used = round_num
        tool_calls.append(call)

        if round_num == max_rounds:
            hit_max = True
            logger.warning("Tool loop hit max rounds (%d), forcing stop", max_rounds)
            tool_results.append(ToolResult(
                tool_name=call.name,
                success=False,
                error="max rounds reached",
            ))
            break

        func = registry.get(call.name)
        if func is None:
            logger.warning("Tool '%s' not found in registry", call.name)
            tool_results.append(ToolResult(
                tool_name=call.name,
                success=False,
                error=f"tool '{call.name}' not found",
            ))
            messages.append({
                "role": "tool",
                "content": json.dumps({"error": f"tool '{call.name}' not found"}, ensure_ascii=False),
            })
            continue

        try:
            result = await func(call.arguments)
            tool_results.append(ToolResult(
                tool_name=call.name,
                success=True,
                data=result,
            ))
            messages.append({
                "role": "tool",
                "content": json.dumps(
                    {"tool": call.name, "result": result},
                    ensure_ascii=False,
                    default=str,
                ),
            })
            logger.info("Tool '%s' executed successfully (round %d)", call.name, round_num)
        except Exception as exc:
            logger.warning("Tool '%s' failed: %s", call.name, exc)
            tool_results.append(ToolResult(
                tool_name=call.name,
                success=False,
                error=str(exc),
            ))
            messages.append({
                "role": "tool",
                "content": json.dumps(
                    {"tool": call.name, "error": str(exc)},
                    ensure_ascii=False,
                ),
            })

    final_output = messages[-1].get("content", "") if messages else ""

    return ToolLoopResult(
        final_output=final_output,
        rounds_used=rounds_used,
        tool_calls=tool_calls,
        tool_results=tool_results,
        hit_max_rounds=hit_max,
    )
