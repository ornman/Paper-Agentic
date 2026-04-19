"""
外部服务连通性测试（调真实 API，需要 .env 配置正确）

- test_embedding_connectivity: 验证硅基流动 Embedding 能连通，返回 1536 维向量
- test_llm_chat_stream:        验证 DeepSeek LLM 能流式对话，返回非空内容
"""

import pytest

from app.clients.embedding_client import EmbeddingClient
from app.clients.llm_client import LLMClient


@pytest.mark.asyncio
async def test_embedding_connectivity():
    embed = EmbeddingClient()
    vec = await embed.embed_single("测试连通性")
    assert len(vec) == 1536
    await embed.close()


@pytest.mark.asyncio
async def test_llm_chat_stream():
    llm = LLMClient()
    chunks = []
    async for chunk in llm.chat_stream([
        {"role": "system", "content": "用一句话回答。"},
        {"role": "user", "content": "1+1等于几？"},
    ]):
        chunks.append(chunk)

    full = "".join(chunks)
    assert len(full) > 0
    await llm.close()
