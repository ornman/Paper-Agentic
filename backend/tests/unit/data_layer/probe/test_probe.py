"""Probe 模块测试

PROBE-U01: 异常路径单测
PROBE-I01: 真实样本探测
"""

from __future__ import annotations

import pytest
from pathlib import Path

from app.data_layer.PDF_preprocessor_data.probe import probe_pdf, ProbeResult


class TestProbeU01:
    """异常路径单测"""

    def test_nonexistent_path_raises_file_not_found(self, tmp_dir):
        """不存在路径抛 FileNotFoundError"""
        fake_path = tmp_dir / "nonexistent.pdf"
        with pytest.raises(FileNotFoundError):
            probe_pdf(fake_path)

    def test_non_pdf_path_raises_value_error(self, tmp_dir):
        """非 PDF 路径抛 ValueError"""
        txt_file = tmp_dir / "test.txt"
        txt_file.write_text("hello")
        with pytest.raises(ValueError, match="不是 PDF 文件"):
            probe_pdf(txt_file)


class TestProbeI01:
    """真实样本探测"""

    def test_probe_zh_pdf(self, zh_pdf):
        """中文 PDF 探测"""
        result = probe_pdf(zh_pdf)

        assert isinstance(result, ProbeResult)
        assert result.page_count > 0
        assert isinstance(result.has_text_layer, bool)
        assert isinstance(result.text_density, float)
        assert isinstance(result.is_scan_like, bool)
        assert isinstance(result.has_images, bool)
        assert isinstance(result.image_count, int)
        assert isinstance(result.has_form_fields, bool)
        assert isinstance(result.has_formula_signals, bool)
        assert isinstance(result.has_table_signals, bool)
        assert result.doc_complexity_level in ("simple", "moderate", "complex")
        assert result.recommended_route in ("A", "B", "C", "D", "E")

    def test_probe_en_pdf(self, en_pdf):
        """英文 PDF 探测"""
        result = probe_pdf(en_pdf)

        assert isinstance(result, ProbeResult)
        assert result.page_count > 0
        assert result.recommended_route in ("A", "B", "C", "D", "E")
