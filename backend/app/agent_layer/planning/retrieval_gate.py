from __future__ import annotations

from ..contracts.query import FrozenTurnSnapshot


def should_retrieve(snapshot: FrozenTurnSnapshot) -> bool:
    if not snapshot.enable_rag:
        return False

    if not snapshot.paper_ids and not snapshot.selection.strip():
        return False

    return True
