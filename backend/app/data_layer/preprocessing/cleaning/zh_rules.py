"""中文清洗规则

中文特有的模式、规则表、OCR/TOC 处理函数。
"""

from __future__ import annotations

import re

from .common import LineRule, RegexRule


# ═══════════════════════════════════════════════════════════════════════════════
# 中文模式常量
# ═══════════════════════════════════════════════════════════════════════════════

COVER_META_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"^分类号[：:]\s*\S+"),
    re.compile(r"^中图分类号[：:]\s*\S+"),
    re.compile(r"^单位代码[：:]\s*\S+"),
    re.compile(r"^密级[：:]\s*\S+"),
    re.compile(r"^学号[：:]\s*\S+"),
    re.compile(r"^UDC[：:]\s*\S+"),
    re.compile(r"^学校代码[：:]\s*\S+"),
    re.compile(r"^文献标志码[：:]\s*\S+"),
    re.compile(r"^文章编号[：:]\s*\S+"),
    re.compile(r"^ISSN[：:]\s*\S+"),
    re.compile(r"^收稿日期[：:]\s*\S+"),
)

INSTITUTION_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"^培养单位"),
    re.compile(r"^专业名称[：:.]"),
    re.compile(r"^指导教师"),
    re.compile(r"^合作导师[：:.]"),
    re.compile(r"^一级学科[：:.]"),
    re.compile(r"^二级学科[：:.]"),
    re.compile(r"^研究方向[：:.]"),
    re.compile(r"^作者[：:]\s*\S+$"),
    re.compile(r"^作者姓名"),
    re.compile(r"^学位授予单位"),
    re.compile(r"^申请学位"),
    re.compile(r"^硕士学位论文$"),
    re.compile(r"^博士学位论文$"),
    re.compile(r"^学士学位论文$"),
    re.compile(r"^\d{4}年\d{1,2}月\d{1,2}日$"),
    re.compile(r"^\d{4}年\d{1,2}月$"),
    re.compile(r"大学学位评定委员会$"),
    re.compile(r"^东北师范大学.*研究生"),
)

TOC_CHAPTER_RE = re.compile(r"^第[一二三四五六七八九十百千\d]+[篇章节部]")

TOC_ENTRY_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"^目\s*录\s*$"),
    re.compile(r"^\s*[一-鿿\w].*[\.\．\…]{2,}\s*\d+\s*$"),
    re.compile(r"^\s*[一-鿿\w].*\.\.\s*[\.\s]*\d+\s*$"),
    re.compile(r"^[一-鿿\w].*\.\.\s*[\.\s]*\d+\s*$"),
    re.compile(r"^[一-鿿\w].*\.\.\s*$"),
)

JOURNAL_HEADER_RE = re.compile(r"^·.{2,40}·\s*$")

CNKI_RE = re.compile(r"^.*中国知网.*cnki.*$", re.MULTILINE)

AUTHOR_BIO_RE = re.compile(r"作者简介[：:].*$", re.MULTILINE)

PAGE_FOOTER_RE = re.compile(r"^第\s*\d+\s*页\s*共\s*\d+\s*页\s*$", re.MULTILINE)

OCR_CJK_SPACE_RE = re.compile(r"([一-鿿])(?:\s+([一-鿿]))+")


# ═══════════════════════════════════════════════════════════════════════════════
# 中文规则表
# ═══════════════════════════════════════════════════════════════════════════════

ZH_LINE_RULES: list[LineRule] = [
    LineRule("中文封面元数据", COVER_META_PATTERNS),
    LineRule("中文机构行", INSTITUTION_PATTERNS),
    LineRule("中文期刊头", (JOURNAL_HEADER_RE,), limit=20, full=True),
    LineRule("中文目录条目", TOC_ENTRY_PATTERNS),
]

ZH_REGEX_RULES: list[RegexRule] = [
    RegexRule("中文页眉页脚", PAGE_FOOTER_RE),
    RegexRule("CNKI水印", CNKI_RE),
    RegexRule("作者简介", AUTHOR_BIO_RE),
]


# ═══════════════════════════════════════════════════════════════════════════════
# 中文复杂函数
# ═══════════════════════════════════════════════════════════════════════════════

def remove_ocr_spaces_chinese(text: str) -> tuple[str, int]:
    """移除 OCR 产生的中文字符间空格（连续 2+ CJK 被空格隔开）"""
    matches = OCR_CJK_SPACE_RE.findall(text)
    text = OCR_CJK_SPACE_RE.sub(lambda m: re.sub(r"\s+", "", m.group(0)), text)
    return text, len(matches)


def fix_heading_ocr_spaces(text: str) -> tuple[str, int]:
    """修复标题内的 OCR 空格（仅 heading 行）"""
    lines = text.split("\n")
    result = []
    fixed = 0
    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match:
            prefix, title = match.group(1), match.group(2)
            new_title = OCR_CJK_SPACE_RE.sub(
                lambda m: re.sub(r"\s+", "", m.group(0)), title,
            )
            if new_title != title:
                fixed += 1
            result.append(f"{prefix} {new_title}")
        else:
            result.append(line)
    return "\n".join(result), fixed


def remove_toc(text: str, metadata: dict | None = None) -> tuple[str, int]:
    """移除目录（metadata 可用时用策略 1，否则用启发式）"""
    if metadata and "content_list" in metadata:
        return _remove_toc_from_content_list(text, metadata["content_list"])
    return _remove_toc_heuristic(text)


def _remove_toc_from_content_list(
    text: str, content_list: list[dict],
) -> tuple[str, int]:
    """利用 content_list 元数据移除目录块（page_idx≤1 且含 30+ TOC 行）"""
    total_removed = 0
    for item in content_list:
        if item.get("type") != "text" or item.get("page_idx", 999) > 1:
            continue
        block_text = item.get("text", "")
        if not block_text:
            continue
        lines = block_text.split("\n")
        toc_count = sum(1 for line in lines if TOC_CHAPTER_RE.match(line.strip()))
        if toc_count >= 30:
            for line in lines:
                stripped = line.strip()
                if stripped and stripped in text:
                    text = text.replace(stripped, "", 1)
                    total_removed += 1
    if total_removed > 0:
        text = re.sub(r"\n{3,}", "\n\n", text)
    return text, total_removed


def _remove_toc_heuristic(text: str) -> tuple[str, int]:
    """启发式检测无点状目录块（连续 10+ TOC 行 → 删除）"""
    lines = text.split("\n")
    result = []
    removed = 0
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not re.match(r"^[日目]\s*[求录]\s*$", stripped):
            result.append(lines[i])
            i += 1
            continue
        toc_lines = [lines[i]]
        j = i + 1
        while j < len(lines):
            s = lines[j].strip()
            if not s:
                k = j + 1
                while k < len(lines) and not lines[k].strip():
                    k += 1
                if k < len(lines) and TOC_CHAPTER_RE.match(lines[k].strip()):
                    toc_lines.extend(lines[j:k])
                    j = k
                    continue
                break
            if TOC_CHAPTER_RE.match(s) or re.match(r"^[一二三四五六七八九十]+[、.]", s):
                toc_lines.append(lines[j])
                j += 1
            else:
                break
        if len(toc_lines) >= 10:
            removed += len(toc_lines)
            i = j
        else:
            result.extend(toc_lines)
            i = j
    return "\n".join(result), removed
