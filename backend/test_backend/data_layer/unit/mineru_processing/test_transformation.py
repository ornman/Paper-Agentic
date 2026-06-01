"""Transformation 模块测试

TRANS-U01: 数据结构契约
TRANS-I01: 不存在文件
TRANS-C01: 中英文转换
"""

from __future__ import annotations

import os
import pytest
from pathlib import Path

from app.data_layer.preprocessing.mineru_processing import convert_pdf, ConversionResult

_mineru_token = os.environ.get("MINERU_API_KEY", "") or os.environ.get("MINERU_TOKEN", "")
requires_mineru = pytest.mark.skipif(not _mineru_token, reason="需要 MINERU_API_KEY 环境变量")


class TestTransU01:
    """数据结构契约"""

    def test_conversion_result_fields(self):
        """ConversionResult 字段与类型符合契约"""
        result = ConversionResult(
            markdown="test",
            metadata={"key": "value"},
            images=[{"page": 1, "path": "/tmp/img.png"}],
            success=True,
            error=None,
            logs=[],
        )
        assert result.markdown == "test"
        assert isinstance(result.metadata, dict)
        assert isinstance(result.images, list)
        assert result.success is True
        assert result.error is None
        assert isinstance(result.logs, list)

    def test_conversion_result_frozen(self):
        """ConversionResult 是不可变的"""
        result = ConversionResult(
            markdown="test", metadata={}, images=[], success=True,
        )
        with pytest.raises(AttributeError):
            result.markdown = "changed"


class TestTransI01:
    """不存在文件"""

    @pytest.mark.asyncio
    async def test_nonexistent_file_returns_failure(self, tmp_dir):
        """不存在文件返回 success=False"""
        fake_path = tmp_dir / "nonexistent.pdf"
        result = await convert_pdf(fake_path)
        assert result.success is False
        assert "不存在" in result.error


class TestTransC01:
    """中英文转换"""

    @requires_mineru
    @pytest.mark.asyncio
    async def test_zh_pdf_convert(self, zh_pdf, tmp_dir):
        """中文 PDF 转换"""
        result = await convert_pdf(zh_pdf, output_dir=tmp_dir)

        assert result.success is True
        assert len(result.markdown) > 0
        assert result.metadata["page_count"] > 0
        assert result.metadata["char_count"] > 0

    @requires_mineru
    @pytest.mark.asyncio
    async def test_en_pdf_convert(self, en_pdf, tmp_dir):
        """英文 PDF 转换"""
        result = await convert_pdf(en_pdf, output_dir=tmp_dir)

        assert result.success is True
        assert len(result.markdown) > 0
        assert result.metadata["page_count"] > 0


class TestPdfSplitter:
    """PDF 拆分工具"""

    def test_page_count_non_pdf_returns_zero(self, tmp_dir):
        """非 PDF 文件 get_pdf_page_count 返回 0"""
        from app.data_layer.preprocessing.mineru_processing.pdf_splitter import get_pdf_page_count

        docx_file = tmp_dir / "test.docx"
        docx_file.write_text("fake content")
        assert get_pdf_page_count(docx_file) == 0

    def test_compute_chunks(self):
        """切分计算"""
        from app.data_layer.preprocessing.mineru_processing.pdf_splitter import compute_chunks

        chunks = compute_chunks(400, max_pages=180)
        assert chunks == ["1-180", "181-360", "361-400"]

    def test_compute_chunks_no_split(self):
        """不需要切分"""
        from app.data_layer.preprocessing.mineru_processing.pdf_splitter import compute_chunks

        chunks = compute_chunks(100, max_pages=180)
        assert chunks == ["1-100"]
