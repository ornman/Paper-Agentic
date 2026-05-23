"""Kimi Coding API 客户端.

实现 VLMClient 和 LLMClient 抽象接口。
必须伪装 User-Agent: claude-code 才能正常使用。
"""

from __future__ import annotations

import base64
from pathlib import Path

import httpx
from pydantic import BaseModel

from app.clients.vlm_client import LLMClient, VLMClient
from app.core.config import get_settings

settings = get_settings()

# API 端点
_API_URL = f"{settings.kimi_base_url}/messages"

# 请求头（必须伪装成 ClaudeCode）
_HEADERS = {
    "x-api-key": settings.kimi_api_key,
    "Content-Type": "application/json",
    "anthropic-version": "2023-06-01",
    "User-Agent": "claude-code",
}

# VLM 提示词 - 论文图表理解（优化版）
# 参考：z_ai-mcp-server 的 DIAGRAM_UNDERSTANDING_PROMPT

_VLM_PROMPT = """你是一个专业的学术文献图表分析专家。你擅长解读学术论文中的各种图表，包括流程图、架构图、UML 图、ER 图、公式推导图、实验结果图等。

<task>
你的任务是分析这张论文图表，提供全面而准确的描述和解释。
</task>

<approach>
首先识别图表类型。不同的图表类型传达不同的信息：
- 流程图：展示步骤顺序、决策点和处理逻辑
- 架构图：展示系统结构、组件关系和数据流
- UML 类图：展示类设计和面向对象结构
- 序列图：展示组件间的交互时序
- ER 图：展示数据库结构和实体关系
- 公式推导图：展示数学推导过程
- 实验结果图：展示数据对比和趋势

仔细观察图表中的所有元素：
- 文本标签：节点、箭头、图例中的所有文字
- 几何形状：不同形状代表不同类型的组件
- 箭头和连线：表示依赖、数据流或控制流
- 颜色和分组：可能表示不同的层次或类别
- 数值和坐标：如果是图表，注意坐标轴和数据

关注组件之间的关系：
- A 调用 B，还是 B 调用 A？（箭头方向）
- 是单向依赖还是双向交互？
- 连接线上是否有标签说明？

识别设计模式：
- 是否是分层架构？
- 是否是微服务架构？
- 是否是事件驱动模式？
- 是否有负载均衡、缓存、副本等？

<critical_requirements>
- 准确性优先：只描述你确实看到的内容
- 不要编造或推断图表中没有的信息
- 如果某些文字模糊不清，明确说明"文字不可辨认"
- 如果图表结构不完整，说明缺失的部分
</critical_requirements>

<output_structure>
按以下结构组织输出：

**图表概览**
- 图表类型：这是什么类型的图表
- 主题内容：图表展示的核心内容
- 表示层次：是高层架构还是详细设计

**组件分析**
列出所有主要组件及其作用：
- 组件A：描述其功能和职责
- 组件B：描述其功能和职责
...

**关系与数据流**
解释组件如何交互：
- A 通过 X 方式调用 B
- B 将数据发送给 C
- 存在循环/反馈：说明其作用

**设计要点**（如适用）
- 架构模式：使用了什么设计模式
- 扩展性设计：如何支持水平扩展
- 容错设计：如何处理故障
- 性能优化：缓存、异步等

**关键细节**
- 重要的标签、数值、公式
- 特殊的符号或约定
- 值得注意的设计决策
</output_structure>"""


class Message(BaseModel):
    """消息模型."""

    role: str
    content: str


class VLMRequest(BaseModel):
    """VLM 请求模型."""

    image_path: Path
    prompt: str = _VLM_PROMPT
    max_tokens: int = 1024
    temperature: float = 0.0


class ChatRequest(BaseModel):
    """聊天请求模型."""

    messages: list[Message]
    max_tokens: int = 2048
    temperature: float = 0.7


class ChatResponse(BaseModel):
    """聊天响应模型."""

    content: str


class KimiVLMClient(VLMClient):
    """Kimi VLM 客户端实现."""

    async def describe_image(
        self,
        image_path: Path | str,
        prompt: str = _VLM_PROMPT,
        max_tokens: int = 1024,
    ) -> str:
        """异步调用 Kimi VLM 描述图片.

        Args:
            image_path: 图片路径（Path对象或字符串）
            prompt: 提示词
            max_tokens: 最大输出 token

        Returns:
            图片描述文本
        """
        return await describe_image_async(image_path, prompt, max_tokens)

    def describe_image_sync(
        self,
        image_path: Path | str,
        prompt: str = _VLM_PROMPT,
        max_tokens: int = 1024,
    ) -> str:
        """同步调用 Kimi VLM 描述图片.

        Args:
            image_path: 图片路径（Path对象或字符串）
            prompt: 提示词
            max_tokens: 最大输出 token

        Returns:
            图片描述文本
        """
        return describe_image(image_path, prompt, max_tokens)


class KimiLLMClient(LLMClient):
    """Kimi LLM 客户端实现."""

    async def chat(
        self,
        messages: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """异步聊天对话.

        Args:
            messages: 消息列表
            max_tokens: 最大输出 token
            temperature: 温度参数

        Returns:
            响应文本
        """
        return await chat_async(
            [Message(**m) for m in messages],
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def chat_stream(
        self,
        messages: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ):
        """流式聊天对话（模拟）.

        Args:
            messages: 消息列表
            max_tokens: 最大输出 token
            temperature: 温度参数

        Yields:
            文本片段
        """
        response = await self.chat(messages, max_tokens, temperature)

        # 模拟分块输出
        chunk_size = 50
        for i in range(0, len(response), chunk_size):
            yield response[i : i + chunk_size]

    def chat_sync(
        self,
        messages: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """同步聊天对话.

        Args:
            messages: 消息列表
            max_tokens: 最大输出 token
            temperature: 温度参数

        Returns:
            响应文本
        """
        return chat(
            [Message(**m) for m in messages],
            max_tokens=max_tokens,
            temperature=temperature,
        )


# 便捷函数
async def describe_image_async(
    image_path: Path | str,
    prompt: str = _VLM_PROMPT,
    max_tokens: int = 1024,
) -> str:
    """异步调用 Kimi VLM 描述图片.

    Args:
        image_path: 图片路径（Path对象或字符串）
        prompt: 提示词
        max_tokens: 最大输出 token

    Returns:
        图片描述文本
    """
    # 确保是Path对象
    if isinstance(image_path, str):
        image_path = Path(image_path)

    suffix = image_path.suffix.lstrip(".")
    media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(
        suffix, "image/jpeg"
    )
    b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")

    payload = {
        "model": settings.kimi_vlm_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            },
        ],
        "max_tokens": max_tokens,
        "temperature": 0.0,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(_API_URL, json=payload, headers=_HEADERS)
        resp.raise_for_status()
        data = resp.json()
        description = "".join(
            b["text"] for b in data["content"] if b["type"] == "text"
        ).strip()
        return description


def describe_image(
    image_path: Path | str,
    prompt: str = _VLM_PROMPT,
    max_tokens: int = 1024,
) -> str:
    """同步调用 Kimi VLM 描述图片.

    Args:
        image_path: 图片路径（Path对象或字符串）
        prompt: 提示词
        max_tokens: 最大输出 token

    Returns:
        图片描述文本
    """
    import asyncio

    return asyncio.run(describe_image_async(image_path, prompt, max_tokens))


async def chat_async(
    messages: list[Message],
    model: str | None = None,
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> str:
    """异步调用 Kimi LLM 聊天.

    Args:
        messages: 消息列表
        model: 模型名称（默认使用配置）
        max_tokens: 最大输出 token
        temperature: 温度参数

    Returns:
        响应文本
    """
    payload = {
        "model": model or settings.kimi_chat_model,
        "messages": [m.model_dump() for m in messages],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(_API_URL, json=payload, headers=_HEADERS)
        resp.raise_for_status()
        data = resp.json()
        content = "".join(
            b["text"] for b in data["content"] if b["type"] == "text"
        ).strip()
        return content


def chat(
    messages: list[Message],
    model: str | None = None,
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> str:
    """同步调用 Kimi LLM 聊天.

    Args:
        messages: 消息列表
        model: 模型名称（默认使用配置）
        max_tokens: 最大输出 token
        temperature: 温度参数

    Returns:
        响应文本
    """
    import asyncio

    return asyncio.run(chat_async(messages, model, max_tokens, temperature))
