"""混合测试：跨文档类型对比

验证不同文档类型（学位论文、政府文档、期刊论文）的清洗效果。

运行: uv run pytest tests/integration/data_layer/test_mineru_cleaning_mixed.py -v -s
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.data_layer.PDF_preprocessor_data.cleaning import clean_mineru_output

PARSED_DIR = Path(__file__).resolve().parents[2] / "output" / "mineru_json_analysis"


def _load(tag: str):
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
    return markdown, metadata


class TestThesisMetadata:
    """学位论文：VR、郜清攀"""

    @pytest.fixture(params=["VR", "郜清攀"])
    def thesis(self, request):
        data = _load(request.param)
        if data is None:
            pytest.skip(f"未解析: {request.param}")
        return request.param, data

    def test_cover_metadata_removed(self, thesis):
        tag, (markdown, metadata) = thesis
        result = clean_mineru_output(markdown, metadata=metadata)
        assert "分类号" not in result.markdown, f"[{tag}] 分类号未移除"
        assert "学号" not in result.markdown, f"[{tag}] 学号未移除"

    def test_institution_lines_removed(self, thesis):
        tag, (markdown, metadata) = thesis
        result = clean_mineru_output(markdown, metadata=metadata)
        assert "培养单位" not in result.markdown, f"[{tag}] 培养单位未移除"
        assert "指导教师" not in result.markdown, f"[{tag}] 指导教师未移除"


class TestGovernmentDoc:
    """政府文档：2018"""

    def test_toc_removed(self):
        data = _load("2018")
        if data is None:
            pytest.skip("未解析: 2018")
        markdown, metadata = data
        result = clean_mineru_output(markdown, metadata=metadata)
        assert "第一篇 规划背景" not in result.markdown, "目录未移除"
        # 正文中的章节标题是合法内容，只验证目录区域被移除
        assert "第三十七章 有序实现乡村振兴  " not in result.markdown, "目录未移除"

    def test_content_preserved(self):
        data = _load("2018")
        if data is None:
            pytest.skip("未解析: 2018")
        markdown, metadata = data
        result = clean_mineru_output(markdown, metadata=metadata)
        # 正文应保留
        paragraphs = [p for p in result.markdown.split("\n\n") if len(p) > 50]
        assert len(paragraphs) >= 5, "正文段落丢失过多"


class TestJournalPaper:
    """期刊论文：刘威"""

    def test_academic_metadata_removed(self):
        data = _load("刘威")
        if data is None:
            pytest.skip("未解析: 刘威")
        markdown, metadata = data
        result = clean_mineru_output(markdown, metadata=metadata)
        assert "文献标志码" not in result.markdown, "文献标志码未移除"
        assert "文章编号" not in result.markdown, "文章编号未移除"

    def test_journal_header_removed(self):
        data = _load("刘威")
        if data is None:
            pytest.skip("未解析: 刘威")
        markdown, metadata = data
        result = clean_mineru_output(markdown, metadata=metadata)
        import re
        assert not re.search(r"^·.+·$", result.markdown, re.MULTILINE), \
            "期刊头未移除"


class TestCrossDocumentMetrics:
    """跨文档指标对比"""

    @pytest.fixture(params=["2018", "VR", "刘威", "郜清攀"])
    def doc(self, request):
        data = _load(request.param)
        if data is None:
            pytest.skip(f"未解析: {request.param}")
        return request.param, data

    def test_reduction_ratio_bounded(self, doc):
        """缩减比例在合理范围内（不过度清洗）"""
        tag, (markdown, metadata) = doc
        result = clean_mineru_output(markdown, metadata=metadata)
        ratio = result.stats["reduction_ratio"]
        assert 0.0 <= ratio <= 0.5, f"[{tag}] 缩减比 {ratio:.1%} 异常"

    def test_cleaning_logs_meaningful(self, doc):
        """清洗日志记录了实际操作"""
        tag, (markdown, metadata) = doc
        result = clean_mineru_output(markdown, metadata=metadata)
        assert len(result.logs) >= 2, f"[{tag}] 日志条目过少"

    def test_no_ocr_spaces_across_all(self, doc):
        """所有文档的 OCR 空格都被修复"""
        tag, (markdown, metadata) = doc
        result = clean_mineru_output(markdown, metadata=metadata)
        assert "摘 要" not in result.markdown, f"[{tag}] OCR 空格未修复"
