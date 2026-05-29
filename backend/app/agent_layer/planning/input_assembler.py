"""输入拼装：将 written_context、selection、prompt 组装为查询"""

from __future__ import annotations

import re


def _get_settings():
    from app.service_layer.config.settings import get_settings
    return get_settings()


def assemble_query(
    prompt: str = "",
    selection: str = "",
    written_context: str = "",
) -> str:
    """将三类输入源拼装为查询文本"""
    parts: list[str] = []
    if prompt:
        parts.append(prompt)
    if selection:
        parts.append(f"用户圈选的文本：{selection}")
    if written_context:
        parts.append(f"用户已写内容：{written_context}")
    return "\n\n".join(parts)


def sanitize_title(raw_title: str, fallback: str) -> str:
    title_max = _get_settings().title_max_length
    title = re.sub(r"\s+", " ", raw_title).strip().strip("\"'`'")
    title = re.split(r"[\n\r。！？.!?]", title, maxsplit=1)[0].strip()
    title = re.sub(r"^(标题|对话标题)\s*[:：]\s*", "", title)
    if not title:
        title = re.sub(r"\s+", " ", fallback).strip()
    return title[:title_max].strip() or fallback[:title_max].strip() or "新对话"


def normalize_snippet(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def truncate_snippet(text: str, max_length: int = 0) -> str:
    if not max_length:
        max_length = _get_settings().source_snippet_max_length
    normalized = normalize_snippet(text)
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 1].rstrip()}…"


def build_source_label(title: str, page: int | None, section: str) -> str:
    parts = [title or "未命名论文"]
    if page and page > 0:
        parts.append(f"第 {page} 页")
    if section:
        parts.append(section)
    return "｜".join(parts)
