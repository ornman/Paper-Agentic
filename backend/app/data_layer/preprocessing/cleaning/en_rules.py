"""英文清洗规则

英文特有的模式和规则表。
"""

from __future__ import annotations

import re

from .common import LineRule, RegexRule


# ═══════════════════════════════════════════════════════════════════════════════
# 英文模式常量
# ═══════════════════════════════════════════════════════════════════════════════

COVER_META_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"^©\s*\d{4}"),
    re.compile(r"^Article history", re.IGNORECASE),
    re.compile(r"^Received\s+\d{1,2}\s+\w+\s+\d{4}"),
    re.compile(r"^Accepted\s+\d{1,2}\s+\w+\s+\d{4}"),
    re.compile(r"^Available online", re.IGNORECASE),
    re.compile(r"^Keywords?\s*[:：]", re.IGNORECASE),
    re.compile(r"^A\s+R\s+T\s+I\s+C\s+L\s+E\s+I\s+N\s+F\s+O"),
    re.compile(r"^A\s+B\s+S\s+T\s+R\s+A\s+C\s+T"),
    re.compile(r"^Corresponding author", re.IGNORECASE),
    re.compile(r"^E-mail\s*[:：]", re.IGNORECASE),
    re.compile(r"^[A-Z][a-z]+ [A-Z][a-z]+\s+[\w.]+@[\w.]+\.\w+$"),
)

INSTITUTION_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"^Research Supervisor", re.IGNORECASE),
    re.compile(r"^Candidate[：:.]", re.IGNORECASE),
    re.compile(r"^College[：:.]", re.IGNORECASE),
    re.compile(r"^Specialty[：:.]", re.IGNORECASE),
    re.compile(r"^Supervisor[：:.]", re.IGNORECASE),
    re.compile(r"^Dissertation Submitted", re.IGNORECASE),
    re.compile(r"^Thesis for Master", re.IGNORECASE),
    re.compile(r"^Dissertation for Doctor", re.IGNORECASE),
    re.compile(r"University.*Degree", re.IGNORECASE),
)

TOC_ENTRY_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"^Table of Contents", re.IGNORECASE),
    re.compile(r"^CONTENTS\s*$", re.IGNORECASE),
)

HEADER_FOOTER_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"^Check for updates$", re.IGNORECASE),
    re.compile(r"^Publisher'?s?\s+note", re.IGNORECASE),
    re.compile(r"^Contents lists? available", re.IGNORECASE),
    re.compile(r"^journal homepage", re.IGNORECASE),
    re.compile(r"^doi\s*:\s*10\.", re.IGNORECASE),
    re.compile(r"^\d+\s*$"),
    re.compile(r"^ORIGINAL\s+PAPER$", re.IGNORECASE),
    re.compile(r"^Original\s+article$", re.IGNORECASE),
    re.compile(r"^REVIEWED\s+BY$", re.IGNORECASE),
    re.compile(r"^OPEN\s+ACCESS$", re.IGNORECASE),
    re.compile(r"^Index\s+\d+\s*$", re.IGNORECASE),
)

JOURNAL_UI_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"^Submit your article to this journal", re.IGNORECASE),
    re.compile(r"^View (?:related )?articles", re.IGNORECASE),
    re.compile(r"^View Crossmark data", re.IGNORECASE),
    re.compile(r"^Article views?:\s*\d+", re.IGNORECASE),
    re.compile(r"^Citing articles?:\s*\d+", re.IGNORECASE),
    re.compile(r"^This page intentionally left blank", re.IGNORECASE),
    re.compile(r"^This article was submitted to\b", re.IGNORECASE),
)

WATERMARK_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"^Copyright[:\s].*(?:Licensee|Publisher|Published by)", re.IGNORECASE),
    re.compile(r"^©?\s*The Author\(s\)\s+\d{4}", re.IGNORECASE),
    re.compile(r"^Disclaimer/Publisher", re.IGNORECASE),
    re.compile(r"^\(c\)\s*\d{4}\s+.*(?:Published by|Licensee)", re.IGNORECASE),
)

BARE_IMAGE_RE = re.compile(
    r"^!\[\]\(images?/[a-f0-9\-]+\.(?:jpg|jpeg|png|gif|bmp|webp)\)\s*$", re.IGNORECASE,
)

TABLE_PLACEHOLDER_RE = re.compile(r"^\[Insert\s+Table\s+\d+.*?\]$", re.IGNORECASE)

HTML_TABLE_TAGS_RE = re.compile(r"</?(?:table|tr|td|th|thead|tbody)\b[^>]*>", re.IGNORECASE)

EN_HEADING_SPACE_RE = re.compile(r"^(#{1,6}\s+)([A-Za-z](?:\s+[A-Za-z]){2,})\s*$", re.MULTILINE)


# ═══════════════════════════════════════════════════════════════════════════════
# 英文规则表
# ═══════════════════════════════════════════════════════════════════════════════

def _fix_heading_space_match(m: re.Match) -> str:
    """英文标题逐字母空格修复"""
    return m.group(1) + m.group(2).replace(" ", "")


EN_LINE_RULES: list[LineRule] = [
    LineRule("英文封面元数据", COVER_META_PATTERNS),
    LineRule("英文机构行", INSTITUTION_PATTERNS),
    LineRule("英文页眉页脚", HEADER_FOOTER_PATTERNS),
    LineRule("英文期刊UI", JOURNAL_UI_PATTERNS),
    LineRule("英文版权声明", WATERMARK_PATTERNS),
    LineRule("裸图片", (BARE_IMAGE_RE,)),
    LineRule("表格占位符", (TABLE_PLACEHOLDER_RE,)),
    LineRule("英文目录条目", TOC_ENTRY_PATTERNS),
]

EN_REGEX_RULES: list[RegexRule] = [
    RegexRule("HTML表格标签", HTML_TABLE_TAGS_RE),
    RegexRule("英文标题空格", EN_HEADING_SPACE_RE, repl=_fix_heading_space_match),
]
