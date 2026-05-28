from __future__ import annotations

import re

from app.agent_layer.contracts.content_block import BlockCitation, BlockParagraph, ContentBlock
from app.agent_layer.contracts.source_card import SourceCard

_CITATION_PATTERN = re.compile(r"\[(\d+)]")


def extract_citations(text: str) -> list[tuple[int, int, int]]:
    return [
        (match.start(), match.end(), int(match.group(1)))
        for match in _CITATION_PATTERN.finditer(text)
    ]


def build_citation_map(
    citations: list[tuple[int, int, int]],
    sources: list[SourceCard],
) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for _, _, index in citations:
        if index not in mapping and 1 <= index <= len(sources):
            mapping[index] = sources[index - 1].id
    return mapping


def inject_citations(
    text: str,
    citations: list[tuple[int, int, int]],
    citation_map: dict[int, str],
) -> list[ContentBlock]:
    if not citations:
        return [BlockParagraph(text=text)]

    block_citations: list[BlockCitation] = []
    clean_parts: list[str] = []
    prev_end = 0

    for start, end, index in citations:
        clean_parts.append(text[prev_end:start])
        prev_end = end
        source_id = citation_map.get(index)
        if source_id:
            block_citations.append(BlockCitation(sourceId=source_id))

    clean_parts.append(text[prev_end:])
    clean_text = "".join(clean_parts)

    return [BlockParagraph(text=clean_text, citations=block_citations or None)]
