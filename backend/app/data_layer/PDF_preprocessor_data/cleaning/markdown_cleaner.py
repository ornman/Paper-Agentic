"""Markdown 清洗器

对 transformation 产出的 markdown 做格式清洗和规范化。

基于真实 PDF 解析数据的问题修复：
1. 表格残留：MarkItDown 会把排版密集页面转成 markdown 表格
2. PUA 字符：Unicode 私有区字符（0xE000-0xF8FF）是字体编码遗留
3. 全角英文字母/数字：PDF 解析器输出的全角字符
4. 逐字拆行：某些 PDF 每个字符单独一行
5. 过多空行：连续空行需要压缩
"""

from __future__ import annotations

import re
import time
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("paper-assistant")

# 乱码检测规则
_GARBLED_PATTERN = re.compile(r"[\x00-\x08\x0e-\x1f]{3,}")
_BREAK_NEWLINES = re.compile(r"\n{6,}")
_BREAK_REPEAT = re.compile(r"([^\s\-\.=\*|_~#])\1{50,}")

# 标题层级检测
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

# 表格残留检测
_TABLE_SEPARATOR = re.compile(r"^\|[\s\-:]+\|[\s\-:]*\|", re.MULTILINE)
_TABLE_ROW = re.compile(r"^\|.+\|$", re.MULTILINE)

# PUA 字符（Unicode 私有区）
_PUA_PATTERN = re.compile(r"[-]")

# 页眉页脚噪音
_PAGE_FOOTER = re.compile(r"^第\s*\d+\s*页\s*共\s*\d+\s*页\s*$", re.MULTILINE)


@dataclass(frozen=True)
class CleaningResult:
    """清洗结果"""
    markdown: str
    stats: dict
    logs: list[dict] = field(default_factory=list)


def clean_markdown(markdown: str) -> CleaningResult:
    """清洗 markdown 文本

    Args:
        markdown: 原始 markdown 文本

    Returns:
        CleaningResult
    """
    logs: list[dict] = []
    t0 = time.perf_counter()
    original_length = len(markdown)

    # 1. 去除 PUA 字符（Unicode 私有区：字体编码遗留）
    markdown, pua_removed = _remove_pua_chars(markdown)
    if pua_removed > 0:
        logs.append(_log("info", f"去除 PUA 字符 {pua_removed} 处"))

    # 2. 去除控制字符
    markdown, control_removed = _remove_control_chars(markdown)
    if control_removed > 0:
        logs.append(_log("info", f"去除控制字符 {control_removed} 处"))

    # 3. 修复乱码碎片
    markdown, garbled_fixed = _fix_garbled_text(markdown)
    if garbled_fixed > 0:
        logs.append(_log("info", f"修复乱码碎片 {garbled_fixed} 处"))

    # 4. 去除表格残留（MarkItDown 在排版密集页面产生的伪表格）
    markdown, table_removed = _remove_table_residue(markdown)
    if table_removed > 0:
        logs.append(_log("info", f"去除表格残留 {table_removed} 行"))

    # 5. 去除页眉页脚噪音
    markdown, footer_removed = _remove_page_footers(markdown)
    if footer_removed > 0:
        logs.append(_log("info", f"去除页眉页脚 {footer_removed} 处"))

    # 6. 统一全角半角（数字和英文字母）
    markdown = _normalize_width(markdown)

    # 7. 先压缩过多空行（为后续合并做准备）
    markdown, empty_compressed = _compress_excessive_empty_lines(markdown)
    if empty_compressed > 0:
        logs.append(_log("info", f"压缩过多空行 {empty_compressed} 处"))

    # 8. 合并逐字拆行（短行合并）
    markdown, merged_lines = _merge_broken_lines(markdown)
    if merged_lines > 0:
        logs.append(_log("info", f"合并碎片行 {merged_lines} 处"))

    # 8.5 合并极短碎片行（跨空行合并 ≤2 字符的行）
    markdown, ultra_merged = _merge_ultra_short_lines(markdown)
    if ultra_merged > 0:
        logs.append(_log("info", f"合并极短碎片行 {ultra_merged} 处"))

    # 9. 标准化换行（最终压缩）
    markdown = _normalize_newlines(markdown)

    # 9. 去除行尾空格
    markdown = _remove_trailing_spaces(markdown)

    # 10. 标准化标题层级
    markdown, headings_normalized = _normalize_headings(markdown)
    if headings_normalized > 0:
        logs.append(_log("info", f"标准化标题层级 {headings_normalized} 处"))

    # 11. 修复重复字符
    markdown, repeat_fixed = _fix_repeated_chars(markdown)
    if repeat_fixed > 0:
        logs.append(_log("info", f"修复重复字符 {repeat_fixed} 处"))

    # 统计
    elapsed = round(time.perf_counter() - t0, 3)
    stats = {
        "original_length": original_length,
        "cleaned_length": len(markdown),
        "reduction_ratio": round(1 - len(markdown) / max(original_length, 1), 3),
        "elapsed_ms": int(elapsed * 1000),
    }

    logs.append(_log("info", f"清洗完成，耗时 {elapsed}s"))

    return CleaningResult(
        markdown=markdown,
        stats=stats,
        logs=logs,
    )


def clean_mineru_output(markdown: str, metadata: dict | None = None) -> CleaningResult:
    """MinerU 输出的专用清洗（14 步流水线）

    Args:
        markdown: MinerU 输出的 markdown
        metadata: MinerU 输出的 JSON 元数据（可选，content_list 用于辅助目录检测）
    """
    logs: list[dict] = []
    t0 = time.perf_counter()
    original_length = len(markdown)

    # 1. 移除封面元数据 + 学术元数据
    markdown, cover_removed = _remove_cover_metadata(markdown)
    if cover_removed > 0:
        logs.append(_log("info", f"移除封面/学术元数据 {cover_removed} 行"))

    # 2. 移除期刊头（中点包裹的期刊名）
    markdown, journal_removed = _remove_journal_header(markdown)
    if journal_removed > 0:
        logs.append(_log("info", f"移除期刊头 {journal_removed} 行"))

    # 3. 移除点状目录
    markdown, toc_removed = _remove_toc_section(markdown)
    if toc_removed > 0:
        logs.append(_log("info", f"移除点状目录 {toc_removed} 行"))

    # 4. 移除无点状目录（政府文档等）
    markdown, toc2_removed = _remove_non_dot_leader_toc(markdown, metadata)
    if toc2_removed > 0:
        logs.append(_log("info", f"移除无点状目录 {toc2_removed} 行"))

    # 5. 移除 CNKI 水印
    markdown, cnki_removed = _remove_cnki_watermark(markdown)
    if cnki_removed > 0:
        logs.append(_log("info", f"移除 CNKI 水印 {cnki_removed} 处"))

    # 6. 移除作者简介块
    markdown, bio_removed = _remove_author_bio(markdown)
    if bio_removed > 0:
        logs.append(_log("info", f"移除作者简介 {bio_removed} 处"))

    # 7. 移除封面机构行
    markdown, inst_removed = _remove_institution_lines(markdown)
    if inst_removed > 0:
        logs.append(_log("info", f"移除封面机构行 {inst_removed} 行"))

    # 8. 移除页眉页脚
    markdown, footer_removed = _remove_page_footers(markdown)
    if footer_removed > 0:
        logs.append(_log("info", f"去除页眉页脚 {footer_removed} 处"))

    # 9. 移除 OCR 中文空格（连续 3+ CJK 字符间的空格）
    markdown, ocr_fixed = _remove_ocr_spaces_in_chinese(markdown)
    if ocr_fixed > 0:
        logs.append(_log("info", f"修复 OCR 中文空格 {ocr_fixed} 处"))

    # 10. 修复标题内空格
    markdown, heading_fixed = _fix_heading_spaces(markdown)
    if heading_fixed > 0:
        logs.append(_log("info", f"修复标题内空格 {heading_fixed} 处"))

    # 11. 空行压缩
    markdown, empty_compressed = _compress_excessive_empty_lines(markdown)
    if empty_compressed > 0:
        logs.append(_log("info", f"压缩过多空行 {empty_compressed} 处"))

    # 12. 标题层级标准化
    markdown, headings_normalized = _normalize_headings(markdown)
    if headings_normalized > 0:
        logs.append(_log("info", f"标准化标题层级 {headings_normalized} 处"))

    # 13. 修复 URL 中的空格
    markdown, url_fixed = _fix_url_spaces(markdown)
    if url_fixed > 0:
        logs.append(_log("info", f"修复 URL 空格 {url_fixed} 处"))

    # 14. 行尾空格
    markdown = _remove_trailing_spaces(markdown)

    elapsed = round(time.perf_counter() - t0, 3)
    stats = {
        "original_length": original_length,
        "cleaned_length": len(markdown),
        "reduction_ratio": round(1 - len(markdown) / max(original_length, 1), 3),
        "elapsed_ms": int(elapsed * 1000),
        "mode": "mineru",
    }

    logs.append(_log("info", f"MinerU 清洗完成，耗时 {elapsed}s"))

    return CleaningResult(
        markdown=markdown,
        stats=stats,
        logs=logs,
    )


# ── MinerU 专用清洗函数 ─────────────────────────────────

# 封面元数据模式（含学术元数据）
_COVER_META_PATTERNS = [
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
]

# 期刊头模式（中点包裹的期刊名，仅匹配文档前部）
_JOURNAL_HEADER_RE = re.compile(r"^·.{2,40}·\s*$")

# OCR 中文空格：连续 2+ 个 CJK 字符被空格隔开
_OCR_CJK_SPACE_RE = re.compile(
    r"([一-鿿])(?:\s+([一-鿿]))+"
)

# 无点状目录：篇章节标题模式
_TOC_CHAPTER_RE = re.compile(
    r"^第[一二三四五六七八九十百千\d]+[篇章节部]"
)

# 封面机构行模式
_INSTITUTION_PATTERNS = [
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
    re.compile(r"^Research Supervisor", re.IGNORECASE),
    re.compile(r"^Candidate[：:.]", re.IGNORECASE),
    re.compile(r"^College[：:.]", re.IGNORECASE),
    re.compile(r"^Specialty[：:.]", re.IGNORECASE),
    re.compile(r"^Supervisor[：:.]", re.IGNORECASE),
    re.compile(r"^Dissertation Submitted", re.IGNORECASE),
    re.compile(r"^硕士学位论文$"),
    re.compile(r"^博士学位论文$"),
    re.compile(r"^学士学位论文$"),
    re.compile(r"^Thesis for Master", re.IGNORECASE),
    re.compile(r"^Dissertation for Doctor", re.IGNORECASE),
    re.compile(r"^\d{4}年\d{1,2}月\d{1,2}日$"),  # 封面日期
    re.compile(r"^\d{4}年\d{1,2}月$"),  # 封面日期
    re.compile(r"大学学位评定委员会$"),
    re.compile(r"University.*Degree", re.IGNORECASE),
    re.compile(r"^东北师范大学.*研究生"),
]

# 目录区域检测
_TOC_START_PATTERNS = [
    re.compile(r"^目\s*录\s*$"),
    re.compile(r"^Table of Contents", re.IGNORECASE),
    re.compile(r"^CONTENTS", re.IGNORECASE),
]

# 目录条目模式（带点号或页码）
_TOC_ENTRY_PATTERN = re.compile(r"^\s*[一-鿿\w].*[\.\．\…]{2,}\s*\d+\s*$")
_TOC_ENTRY_PATTERN2 = re.compile(r"^\s*[一-鿿\w].*\.\.\s*[\.\s]*\d+\s*$")

# CNKI 水印（仅匹配单行）
_CNKI_PATTERN = re.compile(r"^.*中国知网.*cnki.*$", re.MULTILINE)

# 作者简介
_AUTHOR_BIO_PATTERN = re.compile(r"作者简介[：:].*$", re.MULTILINE)

# URL 空格修复
_URL_SPACE_PATTERN = re.compile(r"(https?://\S*)\s+(\S+)")


def _remove_cover_metadata(text: str) -> tuple[str, int]:
    """移除封面元数据行（分类号、单位代码、密级、学号等）

    这些通常出现在论文前几行，是封面排版信息，不是正文内容。
    """
    lines = text.split("\n")
    result = []
    removed = 0

    for line in lines:
        stripped = line.strip()
        if any(p.match(stripped) for p in _COVER_META_PATTERNS):
            removed += 1
            continue
        result.append(line)

    return "\n".join(result), removed


def _remove_toc_section(text: str) -> tuple[str, int]:
    """移除目录条目行（带点号 + 页码的行）

    策略：逐行检测，只删除匹配目录条目模式的行，不做整段删除。
    这样更安全，不会误删正文标题。

    目录条目特征：
    - 包含连续点号 + 页码（如 "第1章绪论.. .. 1"）
    - "摘要...."、"ABSTRACT.. III"
    """
    lines = text.split("\n")
    result = []
    removed = 0

    for line in lines:
        stripped = line.strip()

        # 检测目录开始标题，也删除
        if any(p.match(stripped) for p in _TOC_START_PATTERNS):
            removed += 1
            continue

        # 检测目录条目（带点号 + 页码）
        if stripped and (
            _TOC_ENTRY_PATTERN.match(stripped) or
            _TOC_ENTRY_PATTERN2.match(stripped) or
            re.match(r"^[一-鿿\w].*\.\.\s*[\.\s]*\d+\s*$", stripped) or
            re.match(r"^[一-鿿\w].*\.\.\s*$", stripped)
        ):
            removed += 1
            continue

        # "CONTENTS" 英文目录标题
        if re.match(r"^CONTENTS\s*$", stripped, re.IGNORECASE):
            removed += 1
            continue

        result.append(line)

    return "\n".join(result), removed


def _remove_cnki_watermark(text: str) -> tuple[str, int]:
    """移除 CNKI 水印行"""
    original_len = len(text)
    text = _CNKI_PATTERN.sub("", text)
    # 清理移除后的多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    removed = 1 if len(text) < original_len else 0
    return text, removed


def _remove_author_bio(text: str) -> tuple[str, int]:
    """移除作者简介块

    匹配"作者简介："开头的整行（可能跨多行，直到遇到空行或新段落）。
    """
    original_len = len(text)
    text = _AUTHOR_BIO_PATTERN.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    removed = 1 if len(text) < original_len else 0
    return text, removed


def _remove_institution_lines(text: str) -> tuple[str, int]:
    """移除封面机构行（培养单位、专业名称、指导教师等）"""
    lines = text.split("\n")
    result = []
    removed = 0

    for line in lines:
        stripped = line.strip()
        if any(p.match(stripped) for p in _INSTITUTION_PATTERNS):
            removed += 1
            continue
        result.append(line)

    return "\n".join(result), removed


def _fix_url_spaces(text: str) -> tuple[str, int]:
    """修复 MinerU 输出中 URL 内的空格

    如 "https://www. cnki. net" → "https://www.cnki.net"
    """
    matches = _URL_SPACE_PATTERN.findall(text)
    count = 0
    for url_part, rest in matches:
        original = f"{url_part} {rest}"
        # 移除 URL 中间和末尾的空格
        fixed = url_part.replace(" ", "") + rest.replace(" ", "")
        if fixed != original:
            text = text.replace(original, fixed, 1)
            count += 1
    return text, count


def _remove_journal_header(text: str) -> tuple[str, int]:
    """移除文档前部的期刊头（中点包裹的文本）

    如 "·社会学理论与实践研究·"
    只检查前 20 行，避免误伤正文中的中点符号。
    """
    lines = text.split("\n")
    result = []
    removed = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if i < 20 and _JOURNAL_HEADER_RE.match(stripped):
            removed += 1
            continue
        result.append(line)

    return "\n".join(result), removed


def _remove_ocr_spaces_in_chinese(text: str) -> tuple[str, int]:
    """移除 OCR 产生的中文字符间空格

    如 "摘 要：本文研究了" → "摘要：本文研究了"
    只处理连续 3+ 个 CJK 字符被空格隔开的情况，避免误伤。
    """
    def _fix_match(m: re.Match) -> str:
        # 去掉匹配段中所有空格，拼回连续 CJK
        return re.sub(r"\s+", "", m.group(0))

    new_text = _OCR_CJK_SPACE_RE.sub(_fix_match, text)
    # 统计匹配次数
    matches = _OCR_CJK_SPACE_RE.findall(text)
    return new_text, len(matches)


def _remove_non_dot_leader_toc(
    text: str, metadata: dict | None = None,
) -> tuple[str, int]:
    """移除无点状符号的目录块

    处理政府文档等纯文本目录（如 "第一篇 规划背景"）。

    策略 1（有 metadata）：从 content_list 找 page_idx≤1 的大文本块，
        若含 30+ 行 TOC 模式则整块文本从 markdown 中移除。
    策略 2（无 metadata）：启发式检测连续 TOC 行。
    """
    # 策略 1：利用 content_list metadata
    if metadata and "content_list" in metadata:
        return _remove_toc_from_content_list(text, metadata["content_list"])

    # 策略 2：启发式检测
    return _remove_toc_heuristic(text)


def _remove_toc_from_content_list(
    text: str, content_list: list[dict],
) -> tuple[str, int]:
    """利用 content_list 元数据移除目录块

    找 page_idx≤1 的 text 块，若含大量 TOC 行则从 markdown 中删除对应文本。
    处理所有匹配块（目录可能跨多页）。
    """
    total_removed = 0

    for item in content_list:
        if item.get("type") != "text":
            continue
        if item.get("page_idx", 999) > 1:
            continue

        block_text = item.get("text", "")
        if not block_text:
            continue

        lines = block_text.split("\n")
        toc_count = sum(
            1 for line in lines
            if _TOC_CHAPTER_RE.match(line.strip())
        )

        # 30+ 行 TOC 模式 → 整块是目录
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
    """启发式检测并移除无点状目录块

    规则：找到 目录/日求 标记后，收集连续匹配 TOC 模式的行。
    若 10+ 行连续匹配，整块删除。
    """
    lines = text.split("\n")
    result = []
    removed = 0
    i = 0

    while i < len(lines):
        stripped = lines[i].strip()

        # 检测目录开始标记
        is_toc_marker = bool(re.match(r"^[日目]\s*[求录]\s*$", stripped))
        if not is_toc_marker:
            result.append(lines[i])
            i += 1
            continue

        # 找到目录标记，向后收集 TOC 行
        toc_start = i
        toc_lines = [lines[i]]
        j = i + 1
        while j < len(lines):
            s = lines[j].strip()
            if not s:
                # 空行：看后面是否还有 TOC 行
                k = j + 1
                while k < len(lines) and not lines[k].strip():
                    k += 1
                if k < len(lines) and _TOC_CHAPTER_RE.match(lines[k].strip()):
                    toc_lines.extend(lines[j:k])
                    j = k
                    continue
                break
            if _TOC_CHAPTER_RE.match(s) or re.match(r"^[一二三四五六七八九十]+[、.]", s):
                toc_lines.append(lines[j])
                j += 1
            else:
                break

        # 10+ 行 → 删除整块
        if len(toc_lines) >= 10:
            removed += len(toc_lines)
            i = j
        else:
            result.extend(toc_lines)
            i = j

    return "\n".join(result), removed


def _fix_heading_spaces(text: str) -> tuple[str, int]:
    """修复标题内的 OCR 空格

    如 "## 一 社会治理 维度在城乡融合中的缺席"
    → "## 一社会治理维度在城乡融合中的缺席"
    """
    lines = text.split("\n")
    result = []
    fixed = 0

    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match:
            prefix = match.group(1)
            title = match.group(2)
            # 对标题文本应用 OCR 空格去除（连续 3+ CJK 字符）
            new_title = _OCR_CJK_SPACE_RE.sub(
                lambda m: re.sub(r"\s+", "", m.group(0)), title,
            )
            if new_title != title:
                fixed += 1
            result.append(f"{prefix} {new_title}")
        else:
            result.append(line)

    return "\n".join(result), fixed


def _remove_pua_chars(text: str) -> tuple[str, int]:
    """去除 Unicode 私有区字符（PUA）

    PDF 解析器（如 MarkItDown）在处理某些字体时会输出 PUA 字符，
    这些字符是字体编码遗留，不是有效内容。
    """
    original_len = len(text)
    # 移除 PUA 区域字符：U+E000-U+F8FF
    text = re.sub(r"[-]", "", text)
    removed = original_len - len(text)
    return text, removed


def _remove_table_residue(text: str) -> tuple[str, int]:
    """去除表格残留

    MarkItDown 在处理排版密集的 PDF 页面（封面、目录等）时，
    会将内容错误地转换为 markdown 表格。这些表格通常：
    - 分隔行密集（| --- | --- |）
    - 每个单元格只有 1-2 个字符
    - 不是真正的表格数据，而是表单布局

    策略：检测连续的表格行块，如果平均单元格字符数 < 4，认为是伪表格。
    """
    lines = text.split("\n")
    result = []
    removed = 0
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 检测表格行（以 | 开头，结尾可能有 | 也可能没有）
        if stripped.startswith("|"):
            # 收集连续的表格行
            table_start = i
            table_end = i
            while table_end < len(lines):
                s = lines[table_end].strip()
                if s.startswith("|") or (not s and table_end > table_start):
                    # 表格行或表格内的空行
                    table_end += 1
                else:
                    break

            table_lines = [l for l in lines[table_start:table_end] if l.strip()]

            # 分离分隔行和数据行
            sep_pattern = re.compile(r"^\|[\s\-:]+(\|[\s\-:]+)+")
            data_lines = [l for l in table_lines if not sep_pattern.match(l.strip())]

            # 计算平均每行有效字符数
            total_chars = 0
            for dl in data_lines:
                cells = dl.strip().strip("|").rstrip().split("|")
                for cell in cells:
                    cell_text = cell.strip()
                    total_chars += len(cell_text)

            avg_chars_per_line = total_chars / max(len(data_lines), 1)

            # 如果平均每行有效字符 < 50，认为是伪表格
            # PDF 布局转换产生的表格，单元格内容碎片化严重
            # 真正的数据表格每行通常有 50+ 有效字符
            if avg_chars_per_line < 50 and len(data_lines) >= 2:
                extracted = _extract_text_from_table(data_lines)
                result.extend(extracted)
                removed += len(table_lines) - len(extracted)
                i = table_end
                continue

        result.append(line)
        i += 1

    return "\n".join(result), removed


def _extract_text_from_table(table_data_lines: list[str]) -> list[str]:
    """从伪表格中提取纯文本

    把表格单元格中的碎片文本拼接回正常文本。
    """
    all_fragments = []
    for line in table_data_lines:
        cells = line.strip().strip("|").split("|")
        for cell in cells:
            text = cell.strip()
            if text:
                all_fragments.append(text)

    if not all_fragments:
        return []

    # 拼接所有碎片为一行（中文不需要空格）
    merged = "".join(all_fragments)

    # 按合理长度断行
    result = []
    for i in range(0, len(merged), 80):
        result.append(merged[i:i + 80])

    return result


def _remove_page_footers(text: str) -> tuple[str, int]:
    """去除页眉页脚噪音

    如 "第 1 页  共 38 页"
    """
    original_len = len(text)
    text = re.sub(r"^第\s*\d+\s*页\s*共\s*\d+\s*页\s*$", "", text, flags=re.MULTILINE)
    removed_lines = original_len - len(text)
    # 也清理连续的空行（footer 删除后留下的）
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text, max(removed_lines, 0)


def _compress_excessive_empty_lines(text: str) -> tuple[str, int]:
    """压缩过多空行

    PDF 解析器经常在每行内容之间插入空行，导致：
    - 11页论文有 3542 个空行（46%）

    策略：连续 2+ 空行压缩为 1 个空行。
    """
    original_len = len(text)
    # 连续 2+ 换行压缩为 1 个换行（即保留单个空行作为段落分隔）
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 也压缩连续 2 个换行（即连续 2 个空行）为 1 个
    # 但这可能太激进，先不压缩 2 个空行
    compressed = max(0, (original_len - len(text)) // 2)
    return text, compressed


def _merge_broken_lines(text: str) -> tuple[str, int]:
    """合并碎片行

    PDF 解析器（如 MarkItDown）在处理某些 PDF 时，会把文本拆成
    碎片行（2-6 字符一行），或在每个句子后插入空行。

    策略：
    - 短行（≤10 字符）连续时合并为一行（碎片拼接）
    - 长行（>10 字符）用空行作段落分隔
    - markdown 语法行不参与合并
    """
    _SHORT_THRESHOLD = 10  # 短行阈值

    lines = text.split("\n")
    result = []
    merge_count = 0
    buffer = []

    for line in lines:
        stripped = line.strip()

        # markdown 语法行不参与合并
        if stripped and (stripped.startswith("#") or stripped.startswith("|") or stripped.startswith("```")):
            if buffer:
                merged = "".join(buffer)
                result.append(merged)
                merge_count += 1
                buffer = []
            result.append(line)
            continue

        if stripped:
            is_short = len(stripped) <= _SHORT_THRESHOLD
            if is_short:
                # 短行：累积到 buffer
                buffer.append(stripped)
            else:
                # 长行
                if buffer:
                    # 有累积的短行，先 flush，再开始新行
                    merged = "".join(buffer)
                    result.append(merged)
                    merge_count += 1
                    buffer = []
                result.append(stripped)
        else:
            # 空行：flush buffer
            if buffer:
                merged = "".join(buffer)
                result.append(merged)
                merge_count += 1
                buffer = []
            result.append("")

    # 处理最后的 buffer
    if buffer:
        merged = "".join(buffer)
        result.append(merged)
        merge_count += 1

    return "\n".join(result), merge_count


def _merge_ultra_short_lines(text: str) -> tuple[str, int]:
    """合并极短碎片行（跨空行）

    处理 PDF 解析器产生的逐字拆行问题，如：
        学
        <空行>
        习
        <空行>
        与
        <空行>
        探
        <空行>
        索

    策略：跨空行合并 ≤2 字符的极短行。
    只有遇到长行（>2 字符且非 markdown 语法）或连续 2+ 空行时才 flush。
    """
    _ULTRA_SHORT = 2  # 极短行阈值

    lines = text.split("\n")
    result = []
    merge_count = 0
    buffer = []
    empty_count = 0

    for line in lines:
        stripped = line.strip()

        # markdown 语法行：hard break
        if stripped and (stripped.startswith("#") or stripped.startswith("|") or stripped.startswith("```")):
            if buffer:
                merged = "".join(buffer)
                result.append(merged)
                merge_count += 1
                buffer = []
                empty_count = 0
            result.append(line)
            continue

        if stripped:
            is_ultra_short = len(stripped) <= _ULTRA_SHORT

            if is_ultra_short:
                # 极短行：累积（忽略前面的空行）
                buffer.append(stripped)
                empty_count = 0
            else:
                # 非极短行
                if buffer and empty_count == 0:
                    # 前面没有空行，直接累积
                    buffer.append(stripped)
                elif buffer and empty_count > 0:
                    # 前面有空行
                    # 如果当前行也是短行（≤10字符），继续累积
                    if len(stripped) <= 10:
                        buffer.append(stripped)
                    else:
                        # 长行：flush buffer，当前行独立
                        merged = "".join(buffer)
                        result.append(merged)
                        merge_count += 1
                        buffer = []
                        result.append(stripped)
                else:
                    # buffer 为空
                    result.append(stripped)
                empty_count = 0
        else:
            # 空行
            empty_count += 1
            if empty_count >= 2:
                # 连续 2+ 空行：flush buffer
                if buffer:
                    merged = "".join(buffer)
                    result.append(merged)
                    merge_count += 1
                    buffer = []
                result.append("")

    # 处理最后的 buffer
    if buffer:
        merged = "".join(buffer)
        result.append(merged)
        merge_count += 1

    return "\n".join(result), merge_count


def _remove_control_chars(text: str) -> tuple[str, int]:
    """去除控制字符"""
    original = text
    # 保留 \n \r \t
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    removed = len(original) - len(text)
    return text, removed


def _fix_garbled_text(text: str) -> tuple[str, int]:
    """修复乱码碎片"""
    matches = _GARBLED_PATTERN.findall(text)
    for match in matches:
        text = text.replace(match, " ")
    return text, len(matches)


def _normalize_newlines(text: str) -> str:
    """标准化换行"""
    # 连续 6+ 换行合并为 2 个
    text = _BREAK_NEWLINES.sub("\n\n", text)
    # 连续 3-5 换行合并为 2 个
    text = re.sub(r"\n{3,5}", "\n\n", text)
    return text


def _remove_trailing_spaces(text: str) -> str:
    """去除行尾空格"""
    lines = text.split("\n")
    lines = [line.rstrip() for line in lines]
    return "\n".join(lines)


def _normalize_width(text: str) -> str:
    """统一全角半角

    数字和英文字母统一为半角
    """
    result = []
    for char in text:
        code = ord(char)
        # 全角数字 ０-９ → 半角 0-9
        if 0xFF10 <= code <= 0xFF19:
            result.append(chr(code - 0xFF10 + 0x30))
        # 全角大写Ａ-Ｚ → 半角 A-Z
        elif 0xFF21 <= code <= 0xFF3A:
            result.append(chr(code - 0xFF21 + 0x41))
        # 全角小写ａ-ｚ → 半角 a-z
        elif 0xFF41 <= code <= 0xFF5A:
            result.append(chr(code - 0xFF41 + 0x61))
        else:
            result.append(char)
    return "".join(result)


def _normalize_headings(text: str) -> tuple[str, int]:
    """标准化标题层级

    确保标题层级连续，无跳级。
    """
    lines = text.split("\n")
    normalized = 0
    result = []
    last_level = 0

    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match:
            level = len(match.group(1))
            title = match.group(2).strip()

            # 跳级修正：如果跳级，调整为上一级 + 1
            if level > last_level + 1 and last_level > 0:
                level = last_level + 1
                normalized += 1

            last_level = level
            result.append(f"{'#' * level} {title}")
        else:
            result.append(line)

    return "\n".join(result), normalized


def _fix_repeated_chars(text: str) -> tuple[str, int]:
    """修复重复字符"""
    matches = _BREAK_REPEAT.findall(text)
    for match in matches:
        # 找到重复字符序列并截断
        pattern = re.compile(re.escape(match) + "{50,}")
        text = pattern.sub(match * 3, text)
    return text, len(matches)


def _log(level: str, message: str, **kwargs) -> dict:
    """生成日志条目"""
    import datetime
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "level": level,
        "message": message,
    }
    entry.update(kwargs)
    return entry
