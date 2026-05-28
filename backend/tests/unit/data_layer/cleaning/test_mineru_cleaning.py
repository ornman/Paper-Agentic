"""clean_mineru_output 专用测试

噪音移除 / 幂等性 / 回归 / 内容保护
"""

from __future__ import annotations

import re

import pytest

from app.data_layer.PDF_preprocessor_data.cleaning import clean_mineru_output, CleaningResult


class TestNoiseRemoval:
    """噪音移除：新增的 5 种噪音模式"""

    def test_remove_journal_header(self):
        """期刊头：中点包裹的期刊名"""
        raw = "·社会学理论与实践研究·\n\n# 论文标题\n\n正文内容"
        result = clean_mineru_output(raw)
        assert "·社会学理论与实践研究·" not in result.markdown
        assert "# 论文标题" in result.markdown

    def test_remove_journal_header_only_near_start(self):
        """期刊头：只删前 20 行，正文中的中点不删"""
        lines = ["正文"] * 25 + ["·正文中的中点·"]
        raw = "\n".join(lines)
        result = clean_mineru_output(raw)
        assert "·正文中的中点·" in result.markdown

    def test_remove_academic_metadata(self):
        """学术元数据：文献标志码、文章编号"""
        raw = "文献标志码：A\n\n文章编号：1002－462X（2022）11－0049－11\n\n正文"
        result = clean_mineru_output(raw)
        assert "文献标志码" not in result.markdown
        assert "文章编号" not in result.markdown

    def test_remove_academic_metadata_issn(self):
        """学术元数据：ISSN"""
        raw = "ISSN：1002-462X\n\n正文"
        result = clean_mineru_output(raw)
        assert "ISSN" not in result.markdown

    def test_remove_academic_metadata_zhongtu(self):
        """学术元数据：中图分类号"""
        raw = "中图分类号：C91\n\n正文"
        result = clean_mineru_output(raw)
        assert "中图分类号" not in result.markdown

    def test_remove_ocr_spaces_basic(self):
        """OCR 空格：连续 3+ CJK 字符间的空格"""
        raw = "摘 要：本文研究了城乡融合问题"
        result = clean_mineru_output(raw)
        assert "摘要：" in result.markdown

    def test_remove_ocr_spaces_merges_two_chars(self):
        """OCR 空格：2 个 CJK 字符间的空格也会被合并"""
        raw = "测试 文本"
        result = clean_mineru_output(raw)
        # 阈值是 2+，所以 "测试 文本" → "测试文本"
        assert "测试文本" in result.markdown

    def test_remove_non_dot_leader_toc(self):
        """无点状目录：纯文本篇章节目录"""
        toc_lines = [
            "第一篇 规划背景", "第一章重大意义", "第二章 振兴基础",
            "第三章发展态势", "第二篇总体要求", "第四章 指导思想",
            "第一节 指导思想", "第二节 基本原则", "第五章发展目标",
            "第六章 远景谋划", "第三篇 构建乡村振兴新格局",
            "第七章 统筹城乡发展空间",
        ]
        raw = "日求\n" + "\n".join(toc_lines) + "\n\n## 前言\n\n正文内容"
        result = clean_mineru_output(raw)
        assert "第一篇" not in result.markdown
        assert "前言" in result.markdown

    def test_remove_non_dot_leader_toc_with_metadata(self):
        """无点状目录：通过 content_list metadata 检测"""
        toc_text = "\n".join([
            "第一篇 规划背景", "第一章重大意义", "第二章 振兴基础",
            "第三章发展态势", "第二篇总体要求", "第四章 指导思想",
            "第一节 指导思想", "第二节 基本原则", "第五章发展目标",
            "第六章 远景谋划", "第三篇 构建乡村振兴新格局",
            "第七章 统筹城乡发展空间", "第八章 优化乡村发展布局",
            "第九章 分类推进乡村发展", "第十章 坚决打好精准脱贫攻坚战",
            "第十一章 夯实农业生产能力基础", "第十二章 加快农业转型升级",
            "第十三章建立现代农业经营体系", "第十四章 强化农业科技支撑",
            "第十五章 完善农业支持保护制度", "第十六章 推动农村产业深度融合",
            "第十七章 完善紧密型利益联结机制", "第十八章 激发农村创新创业活力",
            "第十九章 推进农业绿色发展", "第二十章 持续改善农村人居环境",
            "第二十一章 加强乡村生态保护与修复", "第二十二章 加强农村思想道德建设",
            "第二十三章 弘扬中华优秀传统文化", "第二十四章 丰富农村文化生活",
            "第二十五章 加强乡村基础设施建设", "第二十六章 增加农村公共服务供给",
        ])
        metadata = {"content_list": [
            {"type": "text", "text": toc_text, "page_idx": 0},
        ]}
        raw = "日求\n" + toc_text + "\n\n## 前言\n\n正文"
        result = clean_mineru_output(raw, metadata=metadata)
        assert "第一篇" not in result.markdown
        assert "前言" in result.markdown

    def test_fix_heading_spaces(self):
        """标题内空格：OCR 产生的标题空格"""
        raw = "## 一 社会治理 维度在城乡融合中的缺席\n\n正文"
        result = clean_mineru_output(raw)
        # 标题内的连续 CJK 空格应被修复
        assert "## 一社会治理维度在城乡融合中的缺席" in result.markdown


class TestIdempotency:
    """幂等性：清洗两次结果不变"""

    def test_idempotent_full_pipeline(self):
        raw = "·社会学理论与实践研究·\n\n文献标志码：A\n\n摘 要：测试文本\n\n正文"
        result1 = clean_mineru_output(raw)
        result2 = clean_mineru_output(result1.markdown)
        assert result1.markdown == result2.markdown

    def test_idempotent_toc_removal(self):
        toc = "\n".join([f"第{i}章内容" for i in range(1, 15)])
        raw = "日求\n" + toc + "\n\n## 前言\n\n正文"
        result1 = clean_mineru_output(raw)
        result2 = clean_mineru_output(result1.markdown)
        assert result1.markdown == result2.markdown


class TestRegression:
    """回归：已有功能不被破坏"""

    def test_cnki_watermark_removed(self):
        raw = "正文\n\n中国知网 https://www. cnki. net\n\n更多正文"
        result = clean_mineru_output(raw)
        assert "中国知网" not in result.markdown

    def test_cover_metadata_removed(self):
        raw = "分类号：TB47\n\n单位代码：10422\n\n正文"
        result = clean_mineru_output(raw)
        assert "分类号" not in result.markdown
        assert "单位代码" not in result.markdown

    def test_dot_leader_toc_removed(self):
        raw = "摘要.... 1\n第1章绪论.. .. 1\n正文"
        result = clean_mineru_output(raw)
        assert "摘要...." not in result.markdown

    def test_page_footers_removed(self):
        raw = "正文\n\n第 1 页 共 38 页\n\n更多正文"
        result = clean_mineru_output(raw)
        assert "第 1 页" not in result.markdown

    def test_author_bio_removed(self):
        raw = "正文\n\n作者简介：刘威，吉林大学教授。\n\n更多正文"
        result = clean_mineru_output(raw)
        assert "作者简介" not in result.markdown

    def test_url_spaces_fixed(self):
        raw = "参考 https://www. cnki. net 获取更多信息"
        result = clean_mineru_output(raw)
        # _fix_url_spaces 至少修复了一处 URL 空格
        assert any("修复 URL 空格" in log["message"] for log in result.logs)


class TestContentPreservation:
    """内容保护：正文不被误删"""

    def test_preserve_paragraphs(self):
        raw = "乡村振兴战略是党的十九大提出的重大战略。" * 5
        result = clean_mineru_output(raw)
        assert "乡村振兴战略" in result.markdown
        assert len(result.markdown) >= 100

    def test_preserve_references(self):
        raw = "马克思指出［1］，城乡关系是社会发展的基本关系［2］。"
        result = clean_mineru_output(raw)
        assert "［1］" in result.markdown
        assert "［2］" in result.markdown

    def test_preserve_tables(self):
        raw = "| 列1 | 列2 |\n| --- | --- |\n| 数据1 | 数据2 |"
        result = clean_mineru_output(raw)
        assert "数据1" in result.markdown
        assert "数据2" in result.markdown


class TestStructure:
    """CleaningResult 结构"""

    def test_result_has_mode(self):
        result = clean_mineru_output("测试文本")
        assert isinstance(result, CleaningResult)
        assert "mode" in result.stats
        assert result.stats["mode"] == "mineru"

    def test_stats_accurate(self):
        raw = "测试文本内容"
        result = clean_mineru_output(raw)
        assert result.stats["original_length"] == len(raw)
        assert result.stats["cleaned_length"] == len(result.markdown)
