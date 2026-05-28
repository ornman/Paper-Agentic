"""PDF 轻量探针

在导入 PDF 时做快速特征检测，输出路由建议。
不依赖重模型，只用 pypdf / pdfplumber 做轻量分析。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber
from pypdf import PdfReader

logger = logging.getLogger("paper-assistant")

# 公式信号符号
_FORMULA_SYMBOLS = set("∑∫√≤≥×÷αβγδεζηθικλμνξπρστυφχψω∂∇∞≈≠≡∈∉⊂⊃∪∩")
_FORMULA_LATEX = re.compile(r"\\(?:frac|sum|int|sqrt|lim|log|sin|cos|tan|alpha|beta|gamma|delta|lambda|pi|sigma)")
_TABLE_KEYWORDS = re.compile(r"(?:表|Table|Tab)\s*\d+", re.IGNORECASE)
_FORMULA_KEYWORDS = re.compile(r"(?:公式|式|Equation|Eq)\s*[\(\（]?\d+[\)\）]?", re.IGNORECASE)


@dataclass(frozen=True)
class ProbeResult:
    """探针结果"""
    page_count: int
    has_text_layer: bool
    text_density: float  # 平均每页字符数
    is_scan_like: bool
    has_images: bool
    image_count: int
    has_form_fields: bool
    form_field_count: int
    has_formula_signals: bool
    formula_signal_score: float  # 0-1
    has_table_signals: bool
    table_signal_score: float  # 0-1
    doc_complexity_level: str  # "simple" | "moderate" | "complex"
    recommended_route: str  # "A" | "B" | "C" | "D" | "E"
    details: dict = field(default_factory=dict)


def probe_pdf(file_path: Path) -> ProbeResult:
    """对 PDF 做轻量探针，返回特征检测结果"""
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    if file_path.suffix.lower() != ".pdf":
        raise ValueError(f"不是 PDF 文件: {file_path}")

    # 用 pypdf 做基础检测
    pypdf_result = _probe_with_pypdf(file_path)

    # 用 pdfplumber 做深度检测
    plumber_result = _probe_with_pdfplumber(file_path)

    # 合并结果
    page_count = pypdf_result["page_count"]
    has_text_layer = pypdf_result["has_text_layer"]
    total_chars = pypdf_result["total_chars"]
    text_density = total_chars / max(page_count, 1)
    is_scan_like = text_density < 50 and page_count > 2  # 每页不到50字，疑似扫描
    has_form_fields = pypdf_result["has_form_fields"]
    form_field_count = pypdf_result["form_field_count"]

    has_images = plumber_result["has_images"]
    image_count = plumber_result["image_count"]
    has_formula_signals = plumber_result["has_formula_signals"]
    formula_signal_score = plumber_result["formula_signal_score"]
    has_table_signals = plumber_result["has_table_signals"]
    table_signal_score = plumber_result["table_signal_score"]

    # 复杂度判定
    complexity_score = 0
    if is_scan_like:
        complexity_score += 3
    if has_images:
        complexity_score += 1
    if has_form_fields:
        complexity_score += 1
    if has_formula_signals:
        complexity_score += 2
    if has_table_signals:
        complexity_score += 1

    if complexity_score >= 4:
        doc_complexity_level = "complex"
    elif complexity_score >= 2:
        doc_complexity_level = "moderate"
    else:
        doc_complexity_level = "simple"

    # 路由决策
    if is_scan_like:
        recommended_route = "E"  # 扫描件
    elif has_formula_signals and has_form_fields and has_images:
        recommended_route = "D"  # 复杂混合
    elif has_formula_signals or has_form_fields or has_table_signals:
        recommended_route = "C"  # 文字 + 表单/表格/公式
    elif has_images:
        recommended_route = "B"  # 文字 + 图片
    else:
        recommended_route = "A"  # 纯文本

    return ProbeResult(
        page_count=page_count,
        has_text_layer=has_text_layer,
        text_density=text_density,
        is_scan_like=is_scan_like,
        has_images=has_images,
        image_count=image_count,
        has_form_fields=has_form_fields,
        form_field_count=form_field_count,
        has_formula_signals=has_formula_signals,
        formula_signal_score=formula_signal_score,
        has_table_signals=has_table_signals,
        table_signal_score=table_signal_score,
        doc_complexity_level=doc_complexity_level,
        recommended_route=recommended_route,
        details={
            "total_chars": total_chars,
            "pypdf": pypdf_result,
            "pdfplumber": plumber_result,
        },
    )


def _probe_with_pypdf(file_path: Path) -> dict:
    """用 pypdf 做基础检测"""
    result = {
        "page_count": 0,
        "has_text_layer": False,
        "total_chars": 0,
        "has_form_fields": False,
        "form_field_count": 0,
    }

    try:
        reader = PdfReader(str(file_path))
        result["page_count"] = len(reader.pages)

        # 检测文字层
        total_chars = 0
        for page in reader.pages:
            text = page.extract_text() or ""
            total_chars += len(text.strip())
        result["total_chars"] = total_chars
        result["has_text_layer"] = total_chars > 100  # 至少100字才算有文字层

        # 检测表单字段
        if reader.get_fields():
            result["has_form_fields"] = True
            result["form_field_count"] = len(reader.get_fields())

    except Exception as e:
        logger.warning("pypdf 探针失败: %s", e)

    return result


def _probe_with_pdfplumber(file_path: Path) -> dict:
    """用 pdfplumber 做深度检测"""
    result = {
        "has_images": False,
        "image_count": 0,
        "has_formula_signals": False,
        "formula_signal_score": 0.0,
        "has_table_signals": False,
        "table_signal_score": 0.0,
    }

    try:
        with pdfplumber.open(str(file_path)) as pdf:
            image_count = 0
            formula_score = 0.0
            table_score = 0.0
            pages_checked = 0

            for page in pdf.pages[:10]:  # 只检查前10页
                pages_checked += 1

                # 检测图片
                if page.images:
                    image_count += len(page.images)

                # 检测公式信号
                text = page.extract_text() or ""
                if text:
                    # 数学符号
                    symbol_count = sum(1 for ch in text if ch in _FORMULA_SYMBOLS)
                    symbol_ratio = symbol_count / max(len(text), 1)

                    # LaTeX 痕迹
                    latex_matches = _FORMULA_LATEX.findall(text)

                    # 公式关键词
                    formula_kw = _FORMULA_KEYWORDS.findall(text)

                    page_formula_score = min(1.0, symbol_ratio * 10 + len(latex_matches) * 0.2 + len(formula_kw) * 0.1)
                    formula_score += page_formula_score

                    # 检测表格信号
                    table_kw = _TABLE_KEYWORDS.findall(text)
                    # 简单的列对齐检测
                    lines = text.split("\n")
                    aligned_lines = sum(1 for line in lines if len(line.strip()) > 0 and "\t" in line)
                    alignment_ratio = aligned_lines / max(len(lines), 1)

                    page_table_score = min(1.0, len(table_kw) * 0.2 + alignment_ratio * 0.5)
                    table_score += page_table_score

            result["has_images"] = image_count > 0
            result["image_count"] = image_count

            avg_formula_score = formula_score / max(pages_checked, 1)
            avg_table_score = table_score / max(pages_checked, 1)

            result["has_formula_signals"] = avg_formula_score > 0.1
            result["formula_signal_score"] = round(avg_formula_score, 3)
            result["has_table_signals"] = avg_table_score > 0.1
            result["table_signal_score"] = round(avg_table_score, 3)

    except Exception as e:
        logger.warning("pdfplumber 探针失败: %s", e)

    return result
