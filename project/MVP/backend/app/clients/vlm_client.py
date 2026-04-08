"""VLM（视觉语言模型）客户端抽象接口.

支持多种实现：Kimi、OpenAI、Azure 等。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel


class VLMClient(ABC):
    """VLM 客户端抽象接口."""

    @abstractmethod
    async def describe_image(
        self,
        image_path: Path,
        prompt: str = "请描述这张图片",
        max_tokens: int = 1024,
    ) -> str:
        """描述图片内容.

        Args:
            image_path: 图片路径
            prompt: 提示词
            max_tokens: 最大输出 token

        Returns:
            图片描述文本
        """
        ...

    @abstractmethod
    def describe_image_sync(
        self,
        image_path: Path,
        prompt: str = "请描述这张图片",
        max_tokens: int = 1024,
    ) -> str:
        """同步描述图片内容.

        Args:
            image_path: 图片路径
            prompt: 提示词
            max_tokens: 最大输出 token

        Returns:
            图片描述文本
        """
        ...


class LLMClient(ABC):
    """LLM 客户端抽象接口."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """聊天对话.

        Args:
            messages: 消息列表
            max_tokens: 最大输出 token
            temperature: 温度参数

        Returns:
            响应文本
        """
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ):
        """流式聊天对话.

        Args:
            messages: 消息列表
            max_tokens: 最大输出 token
            temperature: 温度参数

        Yields:
            文本片段
        """
        ...

    @abstractmethod
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
        ...
