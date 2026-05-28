"""A/B 集成测试：raw vs cleaned

加载已解析的 MinerU 产出，对每篇 PDF 跑 clean_mineru_output，
验证噪音移除和内容保护。

运行: uv run pytest tests/integration/data_layer/test_mineru_cleaning_ab.py -v -s
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.data_layer.PDF_preprocessor_data.cleaning import clean_mineru_output

PARSED_DIR = Path(__file__).resolve().parents[2] / "output" / "mineru_json_analysis"


def _load_parsed(tag: str):
    """加载已解析产出（优先 zh/ 子目录，fallback 到根目录）"""
    zh_dir = PARSED_DIR / "zh" / tag
    root_dir = PARSED_DIR / tag
    base = zh_dir if (zh_dir / "full.md").exists() else root_dir

    md_path = base / "full.md"
    if not md_path.exists():
        return None

    markdown = md_path.read_text(encoding="utf-8")
    cl_path = base / "content_list.json"
    metadata = {}
    if cl_path.exists():
        metadata["content_list"] = json.loads(cl_path.read_text(encoding="utf-8"))
    return tag, markdown, metadata


# 中文样本
_ZH_TAGS = ["2018", "VR", "刘威", "谭明方", "郜清攀"]
# 英文样本
_EN_TAGS = ["en-1", "en-10", "en-103"]


@pytest.fixture(params=_ZH_TAGS)
def zh_output(request):
    data = _load_parsed(request.param)
    if data is None:
        pytest.skip(f"未解析: {request.param}")
    return data


@pytest.fixture(params=_EN_TAGS)
def en_output(request):
    tag = request.param
    en_dir = PARSED_DIR / "en" / tag
    md_path = en_dir / "full.md"
    if not md_path.exists():
        pytest.skip(f"未解析: {tag}")
    markdown = md_path.read_text(encoding="utf-8")
    cl_path = en_dir / "content_list.json"
    metadata = {}
    if cl_path.exists():
        metadata["content_list"] = json.loads(cl_path.read_text(encoding="utf-8"))
    return tag, markdown, metadata


class TestCleaningAB_ZH:
    """中文 PDF A/B 对比"""

    def test_cleaning_reduces_length(self, zh_output):
        tag, markdown, metadata = zh_output
        result = clean_mineru_output(markdown, metadata=metadata)
        assert len(result.markdown) <= len(markdown), f"[{tag}] 清洗后不应变长"

    def test_no_cnki_watermark(self, zh_output):
        tag, markdown, metadata = zh_output
        result = clean_mineru_output(markdown, metadata=metadata)
        # CNKI 水印行同时含 "中国知网" 和 "cnki"，正文中单独出现的不算
        assert not (
            "中国知网" in result.markdown and "cnki" in result.markdown.lower()
        ), f"[{tag}] CNKI 水印行未移除"

    def test_no_cover_metadata(self, zh_output):
        tag, markdown, metadata = zh_output
        result = clean_mineru_output(markdown, metadata=metadata)
        assert "分类号" not in result.markdown, f"[{tag}] 分类号未移除"
        assert "单位代码" not in result.markdown, f"[{tag}] 单位代码未移除"

    def test_no_journal_header(self, zh_output):
        tag, markdown, metadata = zh_output
        result = clean_mineru_output(markdown, metadata=metadata)
        assert not re.search(r"^·.+·$", result.markdown, re.MULTILINE), \
            f"[{tag}] 期刊头未移除"

    def test_no_academic_metadata(self, zh_output):
        tag, markdown, metadata = zh_output
        result = clean_mineru_output(markdown, metadata=metadata)
        assert "文献标志码" not in result.markdown, f"[{tag}] 文献标志码未移除"
        assert "文章编号" not in result.markdown, f"[{tag}] 文章编号未移除"

    def test_no_ocr_spaces(self, zh_output):
        tag, markdown, metadata = zh_output
        result = clean_mineru_output(markdown, metadata=metadata)
        assert "摘 要" not in result.markdown, f"[{tag}] OCR 空格未修复"

    def test_content_preserved(self, zh_output):
        tag, markdown, metadata = zh_output
        result = clean_mineru_output(markdown, metadata=metadata)
        paragraphs = [p for p in result.markdown.split("\n\n") if len(p) > 100]
        assert len(paragraphs) >= 1, f"[{tag}] 正文段落丢失"

    def test_stats_accurate(self, zh_output):
        tag, markdown, metadata = zh_output
        result = clean_mineru_output(markdown, metadata=metadata)
        assert result.stats["original_length"] == len(markdown)
        assert result.stats["cleaned_length"] == len(result.markdown)
        assert result.stats["mode"] == "mineru"

    def test_reduction_ratio_reasonable(self, zh_output):
        tag, markdown, metadata = zh_output
        result = clean_mineru_output(markdown, metadata=metadata)
        ratio = result.stats["reduction_ratio"]
        assert 0.0 <= ratio <= 0.5, f"[{tag}] 缩减比 {ratio:.1%} 过大"


class TestCleaningAB_EN:
    """英文 PDF A/B 对比"""

    def test_cleaning_reduces_length(self, en_output):
        tag, markdown, metadata = en_output
        result = clean_mineru_output(markdown, metadata=metadata)
        assert len(result.markdown) <= len(markdown), f"[{tag}] 清洗后不应变长"

    def test_no_page_footers(self, en_output):
        tag, markdown, metadata = en_output
        result = clean_mineru_output(markdown, metadata=metadata)
        assert not re.search(r"第\s*\d+\s*页\s*共\s*\d+\s*页", result.markdown), \
            f"[{tag}] 页脚未移除"

    def test_content_preserved(self, en_output):
        tag, markdown, metadata = en_output
        result = clean_mineru_output(markdown, metadata=metadata)
        paragraphs = [p for p in result.markdown.split("\n\n") if len(p) > 100]
        assert len(paragraphs) >= 1, f"[{tag}] 正文段落丢失"
