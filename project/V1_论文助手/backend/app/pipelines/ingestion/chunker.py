"""语义切块器：32k/24k/重叠策略"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.pipelines.ingestion.cleaner import Chunk


@dataclass
class SemanticChunk:
    content: str
    page: int
    section_title: str
    chunk_type: str = "paragraph"
    file_hash: str = ""
    has_image: str = "false"


def estimate_tokens(text: str) -> int:
    """估算 token 数（中文字符 1.5，其他 0.75）"""
    count = 0
    for ch in text:
        count += 1.5 if "\u4e00" <= ch <= "\u9fff" else 0.75
    return int(count)


def chunk_by_semantic_units(
    chunks: list[Chunk],
    max_context: int = 0,
    target_size: int = 0,
    overlap_buffer: int = 0,
) -> list[dict]:
    """对清洗后的 chunk 列表进行语义切块"""
    settings = get_settings()
    max_ctx = max_context or settings.chunk_max_context
    target = target_size or settings.chunk_target_size
    overlap = overlap_buffer or settings.chunk_overlap_buffer

    if not chunks:
        return []

    # 将 Chunk 列表转为带 token 计数的内部格式
    units: list[dict] = []
    for c in chunks:
        units.append({
            "content": c.content,
            "page": c.page,
            "section_title": c.section_title,
            "chunk_type": c.chunk_type,
            "file_hash": c.file_hash,
            "has_image": c.has_image,
            "tokens": estimate_tokens(c.content),
        })

    result: list[dict] = []
    i = 0

    while i < len(units):
        current = units[i]

        # 尝试贪婪合并相邻的小 chunk
        while i + 1 < len(units):
            next_unit = units[i + 1]
            combined_tokens = current["tokens"] + next_unit["tokens"]
            # 加上新行分隔符的 token 开销
            separator_tokens = 2
            if current["tokens"] + separator_tokens + next_unit["tokens"] > max_ctx:
                break
            current = _merge_units(current, next_unit)
            i += 1  # 吞掉 next_unit

        # current 现在是合并后的最大块
        _add_to_result(result, current, max_ctx, target, overlap)
        i += 1

    return result


def _merge_units(a: dict, b: dict) -> dict:
    return {
        "content": a["content"] + "\n\n" + b["content"],
        "page": a["page"],
        "section_title": a["section_title"] + " + " + b["section_title"] if a["section_title"] != b["section_title"] else a["section_title"],
        "chunk_type": a["chunk_type"],
        "file_hash": a.get("file_hash", ""),
        "has_image": a.get("has_image", "false"),
        "tokens": a["tokens"] + b["tokens"],
    }


def _add_to_result(
    result: list[dict],
    unit: dict,
    max_ctx: int,
    target: int,
    overlap: int,
) -> None:
    if unit["tokens"] <= max_ctx:
        result.append(unit)
        return

    # 需要拆分
    content = unit["content"]
    total_chars = len(content)
    n_chunks = max(1, unit["tokens"] // target)
    chars_per_chunk = total_chars // n_chunks

    for ci in range(n_chunks):
        start = ci * chars_per_chunk
        if ci < n_chunks - 1:
            end = start + chars_per_chunk
            # 向后扩展到最近的段落边界
            boundary = content.find("\n\n", end)
            if boundary != -1 and boundary < end + 500:
                end = boundary
        else:
            end = total_chars

        # 添加重叠
        overlap_chars = 0
        if ci > 0:
            overlap_target = int(overlap * (total_chars / max(1, unit["tokens"])))
            overlap_start = max(0, start - overlap_target)
            chunk_content = content[overlap_start:end]
            overlap_chars = start - overlap_start
        else:
            chunk_content = content[start:end]

        result.append({
            "content": chunk_content.strip(),
            "page": unit["page"],
            "section_title": unit["section_title"],
            "chunk_type": unit["chunk_type"],
            "file_hash": unit.get("file_hash", ""),
            "has_image": unit.get("has_image", "false"),
            "tokens": estimate_tokens(chunk_content),
            "chunk_index": ci,
            "total_chunks": n_chunks,
            "is_split": True,
        })
