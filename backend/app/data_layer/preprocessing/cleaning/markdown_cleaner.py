"""Markdown 清洗器 — 数据驱动 + 语言分离

通用引擎在 common.py，中文规则在 zh_rules.py，英文规则在 en_rules.py。
本文件只负责流水线编排。
"""

from __future__ import annotations

import time

from .common import (
    CleaningResult,
    LineRule,
    RegexRule,
    line_filter,
    regex_subs,
    compress_empty_lines,
    normalize_headings,
    fix_url_spaces,
    normalize_width,
    remove_trailing_spaces,
    normalize_newlines,
    remove_table_residue,
    merge_broken_lines,
    merge_ultra_short_lines,
    record,
    log_entry,
)
from . import zh_rules
from . import en_rules


# ═══════════════════════════════════════════════════════════════════════════════
# 通用流水线规则
# ═══════════════════════════════════════════════════════════════════════════════

import re

_GENERIC_REGEX_RULES: list[RegexRule] = [
    RegexRule("PUA字符", re.compile(r"[-]")),
    RegexRule("控制字符", re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")),
    RegexRule("乱码碎片", re.compile(r"[\x00-\x08\x0e-\x1f]{3,}")),
    RegexRule("中文页眉页脚", zh_rules.PAGE_FOOTER_RE),
    RegexRule("重复字符", re.compile(r"([^\s\-\.=\*|_~#])\1{50,}"), repl=lambda m: m.group(1) * 3),
]


# ═══════════════════════════════════════════════════════════════════════════════
# MinerU 专用流水线（中英文混合）
# ═══════════════════════════════════════════════════════════════════════════════

def clean_mineru_output(markdown: str, metadata: dict | None = None) -> CleaningResult:
    """MinerU 输出的专用清洗（中英文规则合并，行级规则单次遍历）"""
    logs: list[dict] = []
    t0 = time.perf_counter()
    original_length = len(markdown)

    # 合并中英文行级规则
    all_line_rules: list[LineRule] = zh_rules.ZH_LINE_RULES + en_rules.EN_LINE_RULES

    # 合并中英文正则规则
    all_regex_rules: list[RegexRule] = zh_rules.ZH_REGEX_RULES + en_rules.EN_REGEX_RULES

    # Phase 1: 行级过滤（单次遍历，批量执行所有规则）
    markdown, n = line_filter(markdown, all_line_rules)
    record(logs, "行级过滤", n)

    # Phase 2: 正则替换
    markdown, n = regex_subs(markdown, all_regex_rules)
    record(logs, "正则替换", n)

    # Phase 3: 复杂逻辑（必须在 OCR 修复之前，否则 CJK 行合并会破坏 TOC 检测）
    markdown, n = zh_rules.remove_toc(markdown, metadata)
    record(logs, "移除目录", n)
    markdown, n = remove_table_residue(markdown)
    record(logs, "去除表格残留", n)

    # Phase 4: OCR 修复（中文专属）
    markdown, n = zh_rules.remove_ocr_spaces_chinese(markdown)
    record(logs, "修复 OCR 中文空格", n)
    markdown, n = zh_rules.fix_heading_ocr_spaces(markdown)
    record(logs, "修复标题内空格", n)

    # Phase 5: 格式化
    markdown, n = compress_empty_lines(markdown)
    record(logs, "压缩过多空行", n)
    markdown, n = normalize_headings(markdown)
    record(logs, "标准化标题层级", n)
    markdown, n = fix_url_spaces(markdown)
    record(logs, "修复 URL 空格", n)
    markdown = remove_trailing_spaces(markdown)

    elapsed = round(time.perf_counter() - t0, 3)
    logs.append(log_entry("info", f"MinerU 清洗完成，耗时 {elapsed}s"))
    return CleaningResult(
        markdown=markdown,
        stats={
            "original_length": original_length,
            "cleaned_length": len(markdown),
            "reduction_ratio": round(1 - len(markdown) / max(original_length, 1), 3),
            "elapsed_ms": int(elapsed * 1000),
            "mode": "mineru",
        },
        logs=logs,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 通用流水线
# ═══════════════════════════════════════════════════════════════════════════════

def clean_markdown(markdown: str) -> CleaningResult:
    """通用 markdown 清洗"""
    logs: list[dict] = []
    t0 = time.perf_counter()
    original_length = len(markdown)

    # Phase 1: 正则替换
    markdown, n = regex_subs(markdown, _GENERIC_REGEX_RULES)
    record(logs, "正则清理", n)

    # Phase 2: 表格残留
    markdown, n = remove_table_residue(markdown)
    record(logs, "去除表格残留", n)

    # Phase 3: 全角半角
    markdown = normalize_width(markdown)

    # Phase 4: 行合并
    markdown, n = compress_empty_lines(markdown)
    record(logs, "压缩过多空行", n)
    markdown, n = merge_broken_lines(markdown)
    record(logs, "合并碎片行", n)
    markdown, n = merge_ultra_short_lines(markdown)
    record(logs, "合并极短碎片行", n)

    # Phase 5: 格式化
    markdown = normalize_newlines(markdown)
    markdown = remove_trailing_spaces(markdown)
    markdown, n = normalize_headings(markdown)
    record(logs, "标准化标题层级", n)

    elapsed = round(time.perf_counter() - t0, 3)
    logs.append(log_entry("info", f"清洗完成，耗时 {elapsed}s"))
    return CleaningResult(
        markdown=markdown,
        stats={
            "original_length": original_length,
            "cleaned_length": len(markdown),
            "reduction_ratio": round(1 - len(markdown) / max(original_length, 1), 3),
            "elapsed_ms": int(elapsed * 1000),
        },
        logs=logs,
    )
