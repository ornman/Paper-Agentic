"""Cleaning 模块测试

CLEAN-U01: 控制字符等定向单测
CLEAN-U02: 全角标点缺口
"""

from __future__ import annotations

import pytest

from app.data_layer.PDF_preprocessor_data.cleaning import clean_markdown, CleaningResult


class TestCleanU01:
    """控制字符等定向单测"""

    def test_remove_control_chars(self):
        """去除控制字符"""
        text = "hello\x00\x01\x02world"
        result = clean_markdown(text)
        assert "\x00" not in result.markdown
        assert "hello" in result.markdown
        assert "world" in result.markdown

    def test_normalize_excessive_newlines(self):
        """超长空行标准化"""
        text = "hello\n\n\n\n\n\n\n\nworld"
        result = clean_markdown(text)
        # 连续 6+ 换行应被合并为 2 个
        assert "\n\n\n\n" not in result.markdown

    def test_fix_repeated_chars(self):
        """重复字符修复"""
        text = "a" * 100
        result = clean_markdown(text)
        # 重复 50+ 次的字符应被截断
        assert len(result.markdown) < 100

    def test_normalize_heading_skip(self):
        """标题跳级修正"""
        text = "# Title\n### Skipped Level"
        result = clean_markdown(text)
        # ### 应被修正为 ##
        assert "## Skipped Level" in result.markdown

    def test_cleaning_result_structure(self):
        """CleaningResult 结构完整"""
        result = clean_markdown("hello world")
        assert isinstance(result, CleaningResult)
        assert isinstance(result.markdown, str)
        assert isinstance(result.stats, dict)
        assert isinstance(result.logs, list)
        assert "original_length" in result.stats
        assert "cleaned_length" in result.stats
        assert "reduction_ratio" in result.stats
        assert "elapsed_ms" in result.stats


class TestCleanU02:
    """全角标点缺口"""

    def test_fullwidth_digits_normalized(self):
        """全角数字转半角"""
        text = "１２３４５"
        result = clean_markdown(text)
        assert result.markdown == "12345"

    def test_fullwidth_letters_normalized(self):
        """全角字母转半角"""
        text = "ＡｂＣ"
        result = clean_markdown(text)
        assert result.markdown == "AbC"

    def test_fullwidth_punctuation_not_normalized(self):
        """全角标点当前未半角化（已知缺口）"""
        text = "，。！？；："
        result = clean_markdown(text)
        # 全角标点仍然保留（这是当前行为，不是 bug）
        assert "，" in result.markdown
