# MinerU 结果清洗入口
# 这里不复用旧 cleaning_service 的 PDF 直读逻辑，原因是当前任务的数据边界已经变了：
# Task 4 的输入是 MinerU 返回的结构化 JSON，而不是本地直接解析 PDF。
#
# 当前只实现计划里要求的四类规则：
# 1. 页眉页脚过滤
# 2. 页码清理
# 3. 短噪音块过滤
# 4. 重复块过滤

from __future__ import annotations

import re
from typing import Any

from app.modules.ingestion.dto import CleanedBlock, CleanedDocument

# 纯页码 / 常见页码格式。
_PAGE_NUMBER_PATTERNS = (
    re.compile(r"^\d{1,4}$"),
    re.compile(r"^第\s*\d{1,4}\s*页$"),
    re.compile(r"^[Pp]age\s*\d{1,4}$"),
    re.compile(r"^[—\-–]\s*\d{1,4}\s*[—\-–]$"),
)

# 带句号的正文大概率不是页眉页脚。
_SENTENCE_PUNCTUATION = set("。！？.!?")

# 过短文本通常是 OCR 噪音、孤立符号、残缺编号。
_MIN_MEANINGFUL_TEXT_LENGTH = 2


def clean_mineru_payload(
    *,
    document_id: str,
    title: str,
    file_path: str,
    index_mode: str,
    payload: dict[str, Any],
) -> CleanedDocument:
    """清洗 MinerU 返回 JSON，并只保留正文块。"""
    raw_blocks = _extract_raw_blocks(payload)
    text_page_counts = _count_distinct_pages_by_text(raw_blocks)

    cleaned_blocks: list[CleanedBlock] = []
    seen_texts: set[str] = set()

    for page, text in raw_blocks:
        if _is_header_or_footer(text, text_page_counts):
            continue
        if _is_page_number(text):
            continue
        if _is_short_noise(text):
            continue
        if text in seen_texts:
            continue

        seen_texts.add(text)
        cleaned_blocks.append(
            CleanedBlock(
                block_id=f"{document_id}_block_{len(cleaned_blocks):04d}",
                page=page,
                text=text,
            )
        )

    return CleanedDocument(
        document_id=document_id,
        title=title,
        file_path=file_path,
        index_mode=index_mode,
        blocks=cleaned_blocks,
        raw_block_count=len(raw_blocks),
        cleaned_block_count=len(cleaned_blocks),
        removed_block_count=len(raw_blocks) - len(cleaned_blocks),
    )


def _extract_raw_blocks(payload: dict[str, Any]) -> list[tuple[int, str]]:
    """从 MinerU payload 中拉平成 (page, text) 列表。"""
    pages = payload.get("pages")
    if not isinstance(pages, list):
        return []

    raw_blocks: list[tuple[int, str]] = []
    for page_item in pages:
        if not isinstance(page_item, dict):
            continue
        page_number = page_item.get("page")
        if not isinstance(page_number, int):
            continue
        blocks = page_item.get("blocks")
        if not isinstance(blocks, list):
            continue

        for block in blocks:
            text = _read_block_text(block)
            if text:
                raw_blocks.append((page_number, text))

    return raw_blocks


def _read_block_text(block: Any) -> str:
    """兼容多种常见字段名，并做统一文本规范化。"""
    if not isinstance(block, dict):
        return ""

    for field_name in ("text", "content", "markdown", "md"):
        value = block.get(field_name)
        if isinstance(value, str):
            return _normalize_text(value)
    return ""


def _normalize_text(text: str) -> str:
    """归一化空白，避免同一块因空格差异绕过去重。"""
    return " ".join(text.split()).strip()


def _count_distinct_pages_by_text(raw_blocks: list[tuple[int, str]]) -> dict[str, int]:
    """统计每段文本出现于多少个不同页面。

    页眉页脚的本质特征不是“出现很多次”，而是“跨页重复出现”。
    因此这里统计的是 distinct page count，而不是原始出现次数。
    """
    text_to_pages: dict[str, set[int]] = {}
    for page, text in raw_blocks:
        text_to_pages.setdefault(text, set()).add(page)
    return {text: len(pages) for text, pages in text_to_pages.items()}


def _is_header_or_footer(text: str, text_page_counts: dict[str, int]) -> bool:
    """识别跨页重复的短行页眉页脚。"""
    if text_page_counts.get(text, 0) < 2:
        return False
    if len(text) > 40:
        return False
    if any(char in _SENTENCE_PUNCTUATION for char in text):
        return False
    return True


def _is_page_number(text: str) -> bool:
    """识别常见页码样式。"""
    return any(pattern.match(text) for pattern in _PAGE_NUMBER_PATTERNS)


def _is_short_noise(text: str) -> bool:
    """过滤极短噪音块。

    这里故意使用很保守的阈值，只删除长度小于等于 2 的文本。
    原因是：
    - Task 4 只要求最小清洗入口。
    - 阈值过大时会误杀真实缩略词、标题编号、术语片段。
    """
    return len(text) <= _MIN_MEANINGFUL_TEXT_LENGTH
