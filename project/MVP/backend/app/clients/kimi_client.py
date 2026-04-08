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

# VLM 提示词
_VLM_PROMPT = """Analyze this academic paper figure. Describe:
1. Figure type (architecture diagram, flowchart, chart, taxonomy tree, etc.)
2. Main components/boxes
3. Connections and data flow between components
4. Key labels and text annotations
5. If it's a chart: what data it shows

Be concise but capture all visual information."""


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
        image_path: Path,
        prompt: str = _VLM_PROMPT,
        max_tokens: int = 1024,
    ) -> str:
        """异步调用 Kimi VLM 描述图片.

        Args:
            image_path: 图片路径
            prompt: 提示词
            max_tokens: 最大输出 token

        Returns:
            图片描述文本
        """
        return await describe_image_async(image_path, prompt, max_tokens)

    def describe_image_sync(
        self,
        image_path: Path,
        prompt: str = _VLM_PROMPT,
        max_tokens: int = 1024,
    ) -> str:
        """同步调用 Kimi VLM 描述图片.

        Args:
            image_path: 图片路径
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
    image_path: Path,
    prompt: str = _VLM_PROMPT,
    max_tokens: int = 1024,
) -> str:
    """异步调用 Kimi VLM 描述图片.

    Args:
        image_path: 图片路径
        prompt: 提示词
        max_tokens: 最大输出 token

    Returns:
        图片描述文本
    """
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
    image_path: Path,
    prompt: str = _VLM_PROMPT,
    max_tokens: int = 1024,
) -> str:
    """同步调用 Kimi VLM 描述图片.

    Args:
        image_path: 图片路径
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
