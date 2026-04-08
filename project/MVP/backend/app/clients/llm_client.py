# LLM 客户端
# 封装 OpenAI 兼容接口，支持流式和非流式输出
from typing import AsyncGenerator
from openai import AsyncOpenAI
from app.core.config import get_settings


class LLMClient:
    """LLM 客户端，支持 OpenAI 兼容协议（DeepSeek / 智谱 / 硅基流动等）"""

    def __init__(self):
        settings = get_settings()
        self._client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
        self._model = settings.llm_model
        self._temperature = settings.llm_temperature
        self._max_tokens = settings.llm_max_tokens

    async def chat(self, messages: list[dict]) -> str:
        """
        非流式问答

        Args:
            messages: OpenAI 格式消息列表 [{"role": "user", "content": "..."}]

        Returns:
            模型输出文本
        """
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            stream=False,
        )
        return response.choices[0].message.content

    async def chat_stream(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        """
        流式问答，返回异步生成器

        Args:
            messages: OpenAI 格式消息列表

        Yields:
            每次流式输出的文本片段
        """
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content is not None:
                yield delta.content
