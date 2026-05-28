"""Embedding token 校验测试

EMB-U01: token 估算
EMB-U02: 超限拒绝
"""

from __future__ import annotations

import pytest

from app.data_layer.indexing.embedding.embedding_client import (
    EmbeddingClient,
    _estimate_tokens,
    MAX_EMBEDDING_TOKENS,
)


class TestEmbU01:
    """token 估算"""

    def test_estimate_tokens_chinese(self):
        """中文字符 1.5 token/字"""
        text = "这是一段中文文本"
        assert _estimate_tokens(text) == int(len(text) * 1.5)

    def test_estimate_tokens_english(self):
        """英文字符 0.75 token/字"""
        text = "hello"
        assert _estimate_tokens(text) == int(len(text) * 0.75)

    def test_estimate_tokens_empty(self):
        """空文本 0 token"""
        assert _estimate_tokens("") == 0


class TestEmbU02:
    """超限拒绝"""

    @pytest.mark.asyncio
    async def test_normal_text_passes(self):
        """正常长度文本不报错"""
        client = EmbeddingClient(
            api_key="fake-key",
            base_url="http://localhost",
            model="test-model",
            dimensions=1536,
            timeout=30.0,
            batch_size=32,
            max_concurrency=5,
        )
        # 不真正调用 API，只测试校验逻辑
        # 用 mock 拦截 _call_api
        from unittest.mock import AsyncMock, patch
        with patch.object(client, "_call_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = [[0.1] * 1536]
            result = await client.embed(["短文本"])
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_oversized_text_raises(self):
        """超长文本应抛出 ValueError"""
        client = EmbeddingClient(
            api_key="fake-key",
            base_url="http://localhost",
            model="test-model",
            dimensions=1536,
            timeout=30.0,
            batch_size=32,
            max_concurrency=5,
        )
        # 构造超长文本：中文字符 * 足够多（每个 1.5 token）
        oversized = "中" * (MAX_EMBEDDING_TOKENS * 2)  # 远超限制
        with pytest.raises(ValueError, match="超出 embedding 模型 token 上限"):
            await client.embed([oversized])

    @pytest.mark.asyncio
    async def test_oversized_in_batch_raises(self):
        """批次中有一个超长文本应抛出 ValueError"""
        client = EmbeddingClient(
            api_key="fake-key",
            base_url="http://localhost",
            model="test-model",
            dimensions=1536,
            timeout=30.0,
            batch_size=32,
            max_concurrency=5,
        )
        normal = "短文本"
        oversized = "中" * (MAX_EMBEDDING_TOKENS * 2)
        with pytest.raises(ValueError, match="text\\[1\\]"):
            await client.embed([normal, oversized])

    @pytest.mark.asyncio
    async def test_embed_single_oversized_raises(self):
        """embed_single 超长文本也应抛出"""
        client = EmbeddingClient(
            api_key="fake-key",
            base_url="http://localhost",
            model="test-model",
            dimensions=1536,
            timeout=30.0,
            batch_size=32,
            max_concurrency=5,
        )
        oversized = "中" * (MAX_EMBEDDING_TOKENS * 2)
        with pytest.raises(ValueError, match="超出 embedding 模型 token 上限"):
            await client.embed_single(oversized)
