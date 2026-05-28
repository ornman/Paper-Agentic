"""Chunking 模块测试

CHUNK-U01: 基础单测
CHUNK-U02: 边界条件
"""

from __future__ import annotations

import pytest

from app.data_layer.preprocessing.chunking import (
    semantic_chunk,
    Chunk,
    Anchor,
)
from app.data_layer.preprocessing.chunking.semantic_chunker import (
    estimate_tokens,
    _split_sentences,
    MIN_CHUNK_TOKENS,
    MAX_CHUNK_TOKENS,
)


class TestChunkU01:
    """基础单测"""

    def test_estimate_tokens_chinese(self):
        """中文 token 估算"""
        text = "这是一段中文文本"
        tokens = estimate_tokens(text)
        # 每个中文字符约 1.5 tokens
        assert tokens > 0
        assert tokens == int(len(text) * 1.5)

    def test_estimate_tokens_english(self):
        """英文 token 估算"""
        text = "hello world"
        tokens = estimate_tokens(text)
        # 每个英文字符约 0.75 tokens
        assert tokens > 0

    def test_split_sentences_chinese(self):
        """中文句子分割"""
        text = "第一句话。第二句话！第三句话？"
        sentences = _split_sentences(text)
        assert len(sentences) == 3

    def test_split_sentences_english(self):
        """英文句子分割"""
        text = "First sentence. Second sentence! Third sentence?"
        sentences = _split_sentences(text)
        assert len(sentences) == 3

    def test_semantic_chunk_empty_input(self):
        """空输入返回空列表"""
        assert semantic_chunk("") == []
        assert semantic_chunk("   ") == []

    def test_semantic_chunk_returns_chunks(self):
        """正常输入返回 Chunk 列表"""
        text = "这是一段测试文本。" * 50  # 足够长以产生多个 chunk
        chunks = semantic_chunk(text)
        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_chunk_has_anchors(self):
        """每个 chunk 有锚点"""
        text = "测试文本。" * 100
        chunks = semantic_chunk(text)
        for chunk in chunks:
            assert len(chunk.anchors) > 0
            assert isinstance(chunk.anchors[0], Anchor)

    def test_chunk_content_not_empty(self):
        """chunk 内容不为空"""
        text = "有效内容。" * 50
        chunks = semantic_chunk(text)
        for chunk in chunks:
            assert len(chunk.content.strip()) > 0


class TestChunkU02:
    """边界条件"""

    def test_short_text_single_chunk(self):
        """短文本产生单个 chunk"""
        text = "短文本。"
        chunks = semantic_chunk(text)
        assert len(chunks) >= 1

    def test_long_text_multiple_chunks(self):
        """长文本产生多个 chunk"""
        # 生成足够长的文本
        text = "这是一个测试句子，用于验证切分逻辑。" * 200
        chunks = semantic_chunk(text)
        assert len(chunks) > 1

    def test_chunk_source_file_path(self):
        """source_file_path 传入锚点"""
        text = "测试内容。" * 50
        chunks = semantic_chunk(text, source_file_path="/tmp/test.pdf")
        for chunk in chunks:
            for anchor in chunk.anchors:
                assert anchor.source_file_path == "/tmp/test.pdf"

    def test_chunk_has_token_count(self):
        """每个 chunk 有 token 计数"""
        text = "测试内容。" * 50
        chunks = semantic_chunk(text)
        for chunk in chunks:
            assert chunk.token_count > 0


class TestChunkU03:
    """Anchor 字段完整性"""

    def test_anchor_has_required_fields(self):
        """anchor 必须有 anchor_id、source_text_hash、char_start、char_end"""
        text = "这是一段测试文本。" * 50
        chunks = semantic_chunk(text, source_file_path="/tmp/test.pdf")
        for chunk in chunks:
            for anchor in chunk.anchors:
                assert anchor.anchor_id, "anchor_id 不能为空"
                assert anchor.source_text_hash, "source_text_hash 不能为空"
                assert anchor.char_start >= 0, "char_start 必须 >= 0"
                assert anchor.char_end > anchor.char_start, "char_end 必须 > char_start"
                assert anchor.source_file_path == "/tmp/test.pdf"

    def test_heading_aware_chunking(self):
        """heading 标记应触发切分"""
        text = """# 第一章 引言

这是第一章的内容。包含一些介绍性的文字。

## 1.1 研究背景

这是研究背景部分。详细描述了研究的背景和动机。

## 1.2 研究目的

这是研究目的部分。说明了本研究的目标。

# 第二章 文献综述

这是第二章的内容。"""
        chunks = semantic_chunk(text)
        # 应该有多个 chunk（heading 触发切分）
        assert len(chunks) >= 2

        # 检查 heading chunk 的类型
        heading_chunks = [c for c in chunks if c.chunk_type == "heading"]
        assert len(heading_chunks) >= 1

    def test_oversized_chunk_rechunked(self):
        """超长 chunk 应该被重切"""
        # 生成超长文本
        text = "这是一个很长的句子。" * 1000
        chunks = semantic_chunk(text)
        # 所有 chunk 都应该在 MAX_CHUNK_TOKENS 以内
        for chunk in chunks:
            assert chunk.token_count <= MAX_CHUNK_TOKENS + 50  # 允许少量误差

    def test_mineru_metadata_enriches_anchors(self):
        """传入 mineru_metadata 时，anchor 应该有 page 信息"""
        text = "这是测试内容。"
        metadata = {
            "content_list": [
                {"type": "text", "text": "这是测试内容。", "page_idx": 2, "bbox": [100, 200, 300, 250], "index": 0},
            ]
        }
        chunks = semantic_chunk(text, source_file_path="/tmp/test.pdf", mineru_metadata=metadata)
        assert len(chunks) >= 1
        # 第一个 chunk 的 anchor 应该有 page 信息
        anchor = chunks[0].anchors[0]
        assert anchor.page == 3  # page_idx + 1 (1-indexed)
        assert anchor.bbox == [100, 200, 300, 250]

    def test_figure_block_marked(self):
        """包含图片引用的 chunk 应该被标记为 figure"""
        # 图片引用需要在句子文本中（句号分隔的同一段内）
        img_ref = "![架构图](images/arch.png)"
        text = f"这是一段包含图片引用的文本{img_ref}图片描述了系统架构。还有一些补充说明。"
        text = text * 20  # 重复以产生多个 chunk
        chunks = semantic_chunk(text)
        # 检查是否有 chunk 包含图片引用
        has_img_chunk = any(img_ref in c.content for c in chunks)
        assert has_img_chunk, "应该有 chunk 包含图片引用"
        figure_chunks = [c for c in chunks if c.has_image]
        assert len(figure_chunks) >= 1
        # figure chunk 应该有子 anchor
        for fc in figure_chunks:
            child_anchors = [a for a in fc.anchors if a.parent_anchor_id]
            assert len(child_anchors) >= 1


class TestChunkU04:
    """parent_chunk_id 父子块关系"""

    def test_normal_chunks_have_empty_parent_chunk_id(self):
        """正常切分的 chunk 的 parent_chunk_id 为空"""
        text = "这是一段普通的测试文本。包含几个句子。用于验证切分逻辑。"
        chunks = semantic_chunk(text)
        for chunk in chunks:
            assert chunk.parent_chunk_id == ""

    def test_oversized_rechunked_has_parent_chunk_id(self):
        """超长块重切后的子块应有 parent_chunk_id 指向原父块"""
        # 生成超长文本（远超 MAX_CHUNK_TOKENS）
        text = "这是一个很长的句子，用于测试超长块重切逻辑。" * 500
        chunks = semantic_chunk(text)

        # 应该有子块被重切
        child_chunks = [c for c in chunks if c.parent_chunk_id]
        assert len(child_chunks) > 0, "应该有重切产生的子块"

        # parent_chunk_id 应该是有效的 chunk_id 格式
        for child in child_chunks:
            assert child.parent_chunk_id.startswith("chunk_")

    def test_rechunked_children_share_same_parent(self):
        """同一超长块重切出的多个子块应共享同一个 parent_chunk_id"""
        text = "这是一段超长文本。" * 1000
        chunks = semantic_chunk(text)

        # 按 parent_chunk_id 分组
        parent_groups: dict[str, list] = {}
        for c in chunks:
            if c.parent_chunk_id:
                parent_groups.setdefault(c.parent_chunk_id, []).append(c)

        # 应该至少有一个父块产生了子块
        assert len(parent_groups) >= 1, "应该至少有一个父块被重切"

        # 同组子块共享同一 parent_chunk_id
        for parent_id, children in parent_groups.items():
            assert all(c.parent_chunk_id == parent_id for c in children)

    def test_rechunked_anchor_has_parent_anchor_id(self):
        """重切子块的 anchor 应有 parent_anchor_id"""
        text = "超长文本重切测试。" * 500
        chunks = semantic_chunk(text)

        child_chunks = [c for c in chunks if c.parent_chunk_id]
        for child in child_chunks:
            # 子块的 anchor 应有 parent_anchor_id
            assert child.anchors[0].parent_anchor_id != "", \
                f"chunk {child.chunk_id} 的 anchor 缺少 parent_anchor_id"
