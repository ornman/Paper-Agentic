from __future__ import annotations

from fastapi import APIRouter

from ..deps import get_sqlite, get_zvec

router = APIRouter(tags=["system"])


@router.get("/health")
async def health_check():
    sqlite = get_sqlite()
    zvec = get_zvec()

    components = {}

    try:
        paper_count = sqlite.get_paper_count()
        components["sqlite"] = {"status": "ok", "paper_count": paper_count}
    except Exception as e:
        components["sqlite"] = {"status": "error", "detail": str(e)}

    try:
        doc_count = zvec.stats.get("doc_count", 0)
        components["zvec"] = {"status": "ok", "doc_count": doc_count}
    except Exception as e:
        components["zvec"] = {"status": "error", "detail": str(e)}

    overall = "ok" if all(
        c.get("status") == "ok" for c in components.values()
    ) else "degraded"

    return {"status": overall, "components": components}
