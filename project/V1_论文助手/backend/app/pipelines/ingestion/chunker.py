"""切块器：固定 1000 tokens 一个 chunk，按段落边界切分"""

from __future__ import annotations

import re

from app.pipelines.ingestion.cleaner import Chunk

CHUNK_SIZE = 1000  # tokens


def estimate_tokens(text: str) -> int:
    """估算 token 数（中文 1.5，其他 0.75）"""
    count = 0
    for ch in text:
        count += 1.5 if "\u4e00" <= ch <= "\u9fff" else 0.75
    return int(count)


def _chars_for_tokens(tokens: int) -> int:
    """粗略估算目标 token 数对应的字符数"""
    return int(tokens / 0.75)


def chunk_text(chunks: list[Chunk], chunk_size: int = CHUNK_SIZE) -> list[dict]:
    """把清洗后的 chunk 列表按 ~chunk_size tokens 切分"""
    if not chunks:
        return []

    # 先合并所有文本，保留章节标记
    sections: list[str] = []
    for c in chunks:
        tag = f"[{c.section_title}]" if c.section_title else ""
        sections.append(f"{tag}\n{c.content}" if tag else c.content)
    full_text = "\n\n".join(sections)

    # 按段落拆分
    paragraphs = re.split(r"\n\n+", full_text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    # 按 chunk_size tokens 组装
    result: list[dict] = []
    buf: list[str] = []
    buf_tokens = 0

    for para in paragraphs:
        para_tokens = estimate_tokens(para)

        # 单个段落就超限，直接切开
        if para_tokens > chunk_size * 2:
            if buf:
                result.append(_make_chunk(buf, len(result)))
                buf = []
                buf_tokens = 0
            for sub in _split_long_para(para, chunk_size):
                result.append(_make_chunk([sub], len(result)))
            continue

        # 加入 buf 后超限，先 flush
        if buf_tokens + para_tokens + 2 > chunk_size and buf:
            result.append(_make_chunk(buf, len(result)))
            buf = []
            buf_tokens = 0

        buf.append(para)
        buf_tokens += para_tokens + 2  # 换行开销

    if buf:
        result.append(_make_chunk(buf, len(result)))

    return result


def _split_long_para(text: str, chunk_size: int) -> list[str]:
    """按句子边界切分超长段落"""
    sentences = re.split(r"(?<=[。！？；.!?;])\s*", text)
    parts: list[str] = []
    buf: list[str] = []
    buf_tokens = 0

    for s in sentences:
        s_tokens = estimate_tokens(s)
        if buf_tokens + s_tokens > chunk_size and buf:
            parts.append("".join(buf))
            buf = []
            buf_tokens = 0
        buf.append(s)
        buf_tokens += s_tokens

    if buf:
        parts.append("".join(buf))
    return parts


def _make_chunk(lines: list[str], index: int) -> dict:
    content = "\n\n".join(lines)
    return {
        "content": content,
        "tokens": estimate_tokens(content),
        "chunk_index": index,
    }
