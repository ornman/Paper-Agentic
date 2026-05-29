from __future__ import annotations

import re

from app.agent_layer.contracts.content_block import (
    BlockCitation,
    BlockCode,
    BlockDivider,
    BlockHeading,
    BlockList,
    BlockParagraph,
    BlockTable,
    ContentBlock,
)
from app.agent_layer.contracts.source_card import SourceCard
from app.agent_layer.response.citation_resolver import (
    build_citation_map,
    extract_citations,
    inject_citations,
)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)")
_UNORDERED_RE = re.compile(r"^[-*]\s+(.*)")
_ORDERED_RE = re.compile(r"^(\d+)\.\s+(.*)")
_TABLE_RE = re.compile(r"^\|(.+)\|$")
_DIVIDER_RE = re.compile(r"^---+$")


def stream_to_blocks(raw_text: str, sources: list[SourceCard]) -> list[ContentBlock]:
    lines = raw_text.split("\n")
    blocks: list[ContentBlock] = []
    list_items: list[str] = []
    list_ordered: bool = False
    table_rows: list[list[str]] = []

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            blocks.append(BlockList(ordered=list_ordered, items=list_items))
            list_items = []

    def flush_table() -> None:
        nonlocal table_rows
        if len(table_rows) >= 2:
            headers = [c.strip() for c in table_rows[0]]
            rows = [[c.strip() for c in row] for row in table_rows[2:]]
            blocks.append(BlockTable(headers=headers, rows=rows))
        elif table_rows:
            for row in table_rows:
                text = " | ".join(c.strip() for c in row)
                blocks.append(_make_paragraph(text, sources))
        table_rows = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # ── Fenced code block (``` or ~~~) ──
        fence_match = re.match(r"^(`{3,}|~{3,})(\w*)", line)
        if fence_match:
            flush_list()
            flush_table()
            fence_char = fence_match.group(1)[0]
            fence_len = len(fence_match.group(1))
            lang = fence_match.group(2) or ""
            code_lines: list[str] = []
            i += 1
            while i < len(lines):
                if lines[i].startswith(fence_char * fence_len) and re.match(
                    rf"^{{{fence_char}}}{{{fence_len},}}\s*$", lines[i]
                ):
                    break
                code_lines.append(lines[i])
                i += 1
            blocks.append(BlockCode(language=lang, code="\n".join(code_lines)))
            i += 1
            continue

        heading_match = _HEADING_RE.match(line)
        if heading_match:
            flush_list()
            flush_table()
            level = min(len(heading_match.group(1)), 4)
            blocks.append(BlockHeading(level=level, text=heading_match.group(2).strip()))
            continue

        if _DIVIDER_RE.match(line):
            flush_list()
            flush_table()
            blocks.append(BlockDivider())
            continue

        table_match = _TABLE_RE.match(line)
        if table_match:
            flush_list()
            cells = table_match.group(1).split("|")
            table_rows.append(cells)
            continue

        if table_rows:
            flush_table()

        unordered_match = _UNORDERED_RE.match(line)
        if unordered_match:
            if list_ordered and list_items:
                flush_list()
            list_ordered = False
            list_items.append(unordered_match.group(1).strip())
            continue

        ordered_match = _ORDERED_RE.match(line)
        if ordered_match:
            if not list_ordered and list_items:
                flush_list()
            list_ordered = True
            list_items.append(ordered_match.group(2).strip())
            continue

        flush_list()

        stripped = line.strip()
        if stripped:
            blocks.append(_make_paragraph(stripped, sources))

        i += 1

    flush_list()
    flush_table()

    return blocks


def _make_paragraph(text: str, sources: list[SourceCard]) -> BlockParagraph:
    citations = extract_citations(text)
    if not citations:
        return BlockParagraph(text=text)
    citation_map = build_citation_map(citations, sources)
    result = inject_citations(text, citations, citation_map)
    return result[0]  # type: ignore[return-value]
