"""Transformation 模块测试

TRANS-U01: 数据结构契约
TRANS-I01: 不存在文件
TRANS-C01: Route A 中英文转换
"""

from __future__ import annotations

import os
import pytest
from pathlib import Path

from app.data_layer.PDF_preprocessor_data.transformation import convert_pdf, ConversionResult

_mineru_token = os.environ.get("MINERU_TOKEN", "")
requires_mineru = pytest.mark.skipif(not _mineru_token, reason="需要 MINERU_TOKEN 环境变量")


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
        result = await convert_pdf(fake_path, route="A")
        assert result.success is False
        assert "不存在" in result.error


class TestTransC01:
    """Route A 中英文转换"""

    @requires_mineru
    @pytest.mark.asyncio
    async def test_zh_pdf_route_a(self, zh_pdf, tmp_dir):
        """中文 Route A 转换"""
        from app.data_layer.PDF_preprocessor_data.probe import probe_pdf
        probe_result = probe_pdf(zh_pdf)

        result = await convert_pdf(
            zh_pdf, route="A", output_dir=tmp_dir, probe_result=probe_result,
        )

        assert result.success is True
        assert len(result.markdown) > 0
        assert result.metadata["page_count"] > 0
        assert result.metadata["route"] == "A"
        assert result.metadata["char_count"] > 0

    @requires_mineru
    @pytest.mark.asyncio
    async def test_en_pdf_route_a(self, en_pdf, tmp_dir):
        """英文 Route A 转换"""
        from app.data_layer.PDF_preprocessor_data.probe import probe_pdf
        probe_result = probe_pdf(en_pdf)

        result = await convert_pdf(
            en_pdf, route="A", output_dir=tmp_dir, probe_result=probe_result,
        )

        assert result.success is True
        assert len(result.markdown) > 0
        assert result.metadata["page_count"] > 0

    @requires_mineru
    @pytest.mark.asyncio
    async def test_metadata_has_probe_data(self, zh_pdf, tmp_dir):
        """验证 metadata 包含 probe 数据"""
        from app.data_layer.PDF_preprocessor_data.probe import probe_pdf

        probe_result = probe_pdf(zh_pdf)
        result = await convert_pdf(
            zh_pdf, route="A", output_dir=tmp_dir, probe_result=probe_result,
        )

        assert result.metadata["page_count"] == probe_result.page_count
        assert "probe" in result.metadata
        assert result.metadata["probe"]["doc_complexity_level"] == probe_result.doc_complexity_level


class TestTransE:
    """Route E 降级处理"""

    @requires_mineru
    @pytest.mark.asyncio
    async def test_route_e_returns_success_with_degraded_flag(self, tmp_dir):
        """Route E 不再硬失败，而是降级成功"""
        # 创建一个模拟扫描件 PDF（用真实 PDF 强制 route=E）
        from app.data_layer.PDF_preprocessor_data.probe import probe_pdf

        # 用任何 PDF，强制 route=E 来测试降级逻辑
        # 需要一个真实存在的 PDF
        from tests.unit.data_layer.conftest import ZH_PDF_DIR
        pdf = next(ZH_PDF_DIR.glob("*.pdf"))

        result = await convert_pdf(pdf, route="E", output_dir=tmp_dir)

        # Route E 现在应该成功（降级）
        assert result.success is True
        assert result.metadata.get("degraded") is True
        assert result.metadata.get("degrade_reason") == "scan_like_ocr_unavailable"
