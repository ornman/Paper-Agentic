from __future__ import annotations

from app.agent_layer.contracts.source_card import SourceCard

_MAX_CONTENT_LENGTH = 220


def map_sources(retrieval_results: list[dict]) -> list[SourceCard]:
    seen_ids: set[str] = set()
    cards: list[SourceCard] = []
    for idx, result in enumerate(retrieval_results):
        paper_id = result.get("paper_id", "")
        chunk_id = result.get("chunk_id", idx)
        source_id = f"src_{paper_id}_{chunk_id}"
        if source_id in seen_ids:
            source_id = f"src_{paper_id}_{chunk_id}_{idx}"
        seen_ids.add(source_id)

        content = result.get("content", "")
        if content and len(content) > _MAX_CONTENT_LENGTH:
            content = content[:_MAX_CONTENT_LENGTH] + "…"

        cards.append(
            SourceCard(
                id=source_id,
                paper_id=paper_id or None,
                title=result.get("title", "未命名论文"),
                page=result.get("page"),
                section=result.get("section"),
                content=content or None,
            )
        )
    return cards
