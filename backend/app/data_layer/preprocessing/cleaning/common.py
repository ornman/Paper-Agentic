"""清洗器通用基础

语言无关的引擎、规则数据类、格式化工具。
各语言规则模块 import 本模块。
"""

from __future__ import annotations

import re
import time
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("paper-assistant")


# ═══════════════════════════════════════════════════════════════════════════════
# 结果类型
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CleaningResult:
    """清洗结果"""
    markdown: str
    stats: dict
    logs: list[dict] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# 规则数据类
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class LineRule:
    """行级过滤规则：匹配 → 删除整行"""
    name: str
    patterns: tuple[re.Pattern, ...]
    limit: int | None = None
    full: bool = False


@dataclass(frozen=True)
class RegexRule:
    """正则替换规则：pattern.subn → 替换"""
    name: str
    pattern: re.Pattern
    repl: str | callable | None = None


# ═══════════════════════════════════════════════════════════════════════════════
# 通用引擎
# ═══════════════════════════════════════════════════════════════════════════════

def line_filter(text: str, rules: list[LineRule]) -> tuple[str, int]:
    """单次遍历，批量执行所有行级过滤规则"""
    lines = text.split("\n")
    result = []
    removed = 0
    for i, line in enumerate(lines):
        s = line.strip()
        matched = False
        if s:
            for rule in rules:
                if rule.limit is not None and i >= rule.limit:
                    continue
                for p in rule.patterns:
                    if (rule.full and p.fullmatch(s)) or (not rule.full and p.search(s)):
                        matched = True
                        break
                if matched:
                    break
        if matched:
            removed += 1
        else:
            result.append(line)
    return "\n".join(result), removed


def regex_subs(text: str, rules: list[RegexRule]) -> tuple[str, int]:
    """批量执行正则替换规则"""
    total = 0
    for rule in rules:
        text, n = rule.pattern.subn(rule.repl or "", text)
        total += n
    return text, total


# ═══════════════════════════════════════════════════════════════════════════════
# 通用格式化工具
# ═══════════════════════════════════════════════════════════════════════════════

_BREAK_NEWLINES_RE = re.compile(r"\n{6,}")
_BREAK_REPEAT_RE = re.compile(r"([^\s\-\.=\*|_~#])\1{50,}")
_GARBLED_RE = re.compile(r"[\x00-\x08\x0e-\x1f]{3,}")
_URL_SPACE_RE = re.compile(r"(https?://\S*)\s+(\S+)")


def compress_empty_lines(text: str) -> tuple[str, int]:
    """压缩连续 2+ 空行为 1 个空行"""
    original = len(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text, max(0, (original - len(text)) // 2)


def normalize_headings(text: str) -> tuple[str, int]:
    """标准化标题层级（修正跳级）"""
    lines = text.split("\n")
    result = []
    normalized = 0
    last_level = 0
    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match:
            level = len(match.group(1))
            title = match.group(2).strip()
            if level > last_level + 1 and last_level > 0:
                level = last_level + 1
                normalized += 1
            last_level = level
            result.append(f"{'#' * level} {title}")
        else:
            result.append(line)
    return "\n".join(result), normalized


def fix_url_spaces(text: str) -> tuple[str, int]:
    """修复 URL 中的空格"""
    count = 0

    def _fix(m: re.Match) -> str:
        nonlocal count
        count += 1
        return m.group(0).replace(" ", "")

    while True:
        new_text = _URL_SPACE_RE.sub(_fix, text)
        if new_text == text:
            break
        text = new_text
    return text, count


def normalize_width(text: str) -> str:
    """统一全角半角（数字和英文字母 → 半角）"""
    result = []
    for char in text:
        code = ord(char)
        if 0xFF10 <= code <= 0xFF19:
            result.append(chr(code - 0xFF10 + 0x30))
        elif 0xFF21 <= code <= 0xFF3A:
            result.append(chr(code - 0xFF21 + 0x41))
        elif 0xFF41 <= code <= 0xFF5A:
            result.append(chr(code - 0xFF41 + 0x61))
        else:
            result.append(char)
    return "".join(result)


def remove_trailing_spaces(text: str) -> str:
    """去除行尾空格"""
    return "\n".join(line.rstrip() for line in text.split("\n"))


def normalize_newlines(text: str) -> str:
    """标准化换行（6+ 换行压缩为 2 个）"""
    text = _BREAK_NEWLINES_RE.sub("\n\n", text)
    return re.sub(r"\n{3,}", "\n\n", text)


def remove_table_residue(text: str) -> tuple[str, int]:
    """去除表格残留（排版密集页面产生的伪表格）"""
    lines = text.split("\n")
    result = []
    removed = 0
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("|"):
            table_start = i
            table_end = i
            while table_end < len(lines):
                s = table_end < len(lines) and lines[table_end].strip()
                if s.startswith("|") or (not s and table_end > table_start):
                    table_end += 1
                else:
                    break
            table_lines = [l for l in lines[table_start:table_end] if l.strip()]
            sep_pattern = re.compile(r"^\|[\s\-:]+(\|[\s\-:]+)+")
            data_lines = [l for l in table_lines if not sep_pattern.match(l.strip())]
            total_chars = sum(
                len(cell.strip())
                for dl in data_lines
                for cell in dl.strip().strip("|").rstrip().split("|")
            )
            avg = total_chars / max(len(data_lines), 1)
            if avg < 50 and len(data_lines) >= 2:
                extracted = _extract_text_from_table(data_lines)
                result.extend(extracted)
                removed += len(table_lines) - len(extracted)
                i = table_end
                continue
        result.append(lines[i])
        i += 1
    return "\n".join(result), removed


def _extract_text_from_table(table_data_lines: list[str]) -> list[str]:
    """从伪表格中提取纯文本"""
    fragments = [
        cell.strip()
        for line in table_data_lines
        for cell in line.strip().strip("|").split("|")
        if cell.strip()
    ]
    if not fragments:
        return []
    merged = "".join(fragments)
    return [merged[i:i + 80] for i in range(0, len(merged), 80)]


def merge_broken_lines(text: str) -> tuple[str, int]:
    """合并碎片行（≤10 字符的连续短行拼接）"""
    _SHORT = 10
    lines = text.split("\n")
    result = []
    merge_count = 0
    buffer: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and (stripped[0] in "#|`" or stripped.startswith("```")):
            if buffer:
                result.append("".join(buffer))
                merge_count += 1
                buffer = []
            result.append(line)
            continue
        if stripped:
            if len(stripped) <= _SHORT:
                buffer.append(stripped)
            else:
                if buffer:
                    result.append("".join(buffer))
                    merge_count += 1
                    buffer = []
                result.append(stripped)
        else:
            if buffer:
                result.append("".join(buffer))
                merge_count += 1
                buffer = []
            result.append("")
    if buffer:
        result.append("".join(buffer))
        merge_count += 1
    return "\n".join(result), merge_count


def merge_ultra_short_lines(text: str) -> tuple[str, int]:
    """合并极短碎片行（跨空行，≤2 字符）"""
    _ULTRA = 2
    lines = text.split("\n")
    result = []
    merge_count = 0
    buffer: list[str] = []
    empty_count = 0
    for line in lines:
        stripped = line.strip()
        if stripped and (stripped[0] in "#|`" or stripped.startswith("```")):
            if buffer:
                result.append("".join(buffer))
                merge_count += 1
                buffer = []
                empty_count = 0
            result.append(line)
            continue
        if stripped:
            if len(stripped) <= _ULTRA:
                buffer.append(stripped)
                empty_count = 0
            else:
                if buffer and empty_count == 0:
                    buffer.append(stripped)
                elif buffer and empty_count > 0:
                    if len(stripped) <= 10:
                        buffer.append(stripped)
                    else:
                        result.append("".join(buffer))
                        merge_count += 1
                        buffer = []
                        result.append(stripped)
                else:
                    result.append(stripped)
                empty_count = 0
        else:
            empty_count += 1
            if empty_count >= 2:
                if buffer:
                    result.append("".join(buffer))
                    merge_count += 1
                    buffer = []
                result.append("")
    if buffer:
        result.append("".join(buffer))
        merge_count += 1
    return "\n".join(result), merge_count


# ═══════════════════════════════════════════════════════════════════════════════
# 日志工具
# ═══════════════════════════════════════════════════════════════════════════════

def log_entry(level: str, message: str) -> dict:
    import datetime
    return {"timestamp": datetime.datetime.now().isoformat(), "level": level, "message": message}


def record(logs: list[dict], message: str, count: int) -> None:
    if count > 0:
        logs.append(log_entry("info", f"{message} {count} 处"))
