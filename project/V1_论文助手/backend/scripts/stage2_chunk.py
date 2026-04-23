"""阶段2：从 parsed JSON → 切块 → 保存到 data/chunks/{paper_id}.json

用法:
    uv run python scripts/stage2_chunk.py
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.pipelines.ingestion.chunker import chunk_text
from app.pipelines.ingestion.cleaner import Chunk
from app.stores.sqlite_repo import SQLiteRepo
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("stage2_chunk")

PARSED_DIR = "./data/parsed"
CHUNKS_DIR = "./data/chunks"


def stage2_chunk_one(
    paper_id: str,
    sqlite: SQLiteRepo,
) -> dict:
    """单篇论文切块"""

    # 检查是否已经切块
    chunks_path = os.path.join(CHUNKS_DIR, f"{paper_id}.json")
    if os.path.exists(chunks_path):
        logger.info("跳过 (chunks JSON 存在): %s", paper_id[:8])
        _update_stage(sqlite, paper_id, "chunked")
        return {"status": "skipped", "paper_id": paper_id}

    # 读取 parsed JSON
    parsed_path = os.path.join(PARSED_DIR, f"{paper_id}.json")
    if not os.path.exists(parsed_path):
        logger.warning("parsed JSON 不存在: %s", paper_id[:8])
        return {"status": "skipped", "paper_id": paper_id, "reason": "no parsed file"}

    with open(parsed_path, "r", encoding="utf-8") as f:
        parsed_data = json.load(f)

    # 重建 Chunk 对象
    chunks = [
        Chunk(
            chunk_id=c["chunk_id"],
            content=c["content"],
            page=c.get("page", 0),
            chunk_type=c.get("chunk_type", "paragraph"),
            section_title=c.get("section_title", ""),
            section_level=c.get("section_level", 0),
            file_hash=parsed_data.get("file_hash", ""),
            has_image=c.get("has_image", "false"),
        )
        for c in parsed_data["chunks"]
    ]

    if not chunks:
        _update_stage(sqlite, paper_id, "failed", "parsed JSON 无 chunks")
        return {"status": "failed", "paper_id": paper_id, "error": "无语义块"}

    # 切块
    chunked = chunk_text(chunks)
    if not chunked:
        _update_stage(sqlite, paper_id, "failed", "切块后为空")
        return {"status": "failed", "paper_id": paper_id, "error": "切块后为空"}

    # 保存 chunks JSON
    os.makedirs(CHUNKS_DIR, exist_ok=True)
    chunked_data = {
        "paper_id": paper_id,
        "file_path": parsed_data.get("file_path", ""),
        "file_hash": parsed_data.get("file_hash", ""),
        "title": parsed_data.get("title", ""),
        "chunks": chunked,
        "mineru_task_id": parsed_data.get("mineru_task_id", ""),
        "paper_dir": parsed_data.get("paper_dir", ""),
    }

    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump(chunked_data, f, ensure_ascii=False, indent=2)

    # 更新状态
    _update_stage(sqlite, paper_id, "chunked")

    logger.info("O %s → %d chunks", paper_id[:8], len(chunked))
    return {"status": "ok", "paper_id": paper_id, "chunks": len(chunked)}


def _update_stage(
    sqlite: SQLiteRepo,
    paper_id: str,
    stage: str,
    error_msg: str | None = None,
) -> None:
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    with sqlite.get_session() as session:
        session.execute(text("""
            UPDATE import_progress
            SET stage = :stage, error_msg = :err, updated_at = :time
            WHERE paper_id = :pid
        """), {"pid": paper_id, "stage": stage, "err": error_msg, "time": now})
        session.commit()


def list_papers_by_stage(sqlite: SQLiteRepo, stage: str) -> list[str]:
    with sqlite.get_session() as session:
        rows = session.execute(
            text("SELECT paper_id FROM import_progress WHERE stage = :stage"),
            {"stage": stage},
        ).fetchall()
        return [row[0] for row in rows]


def main():
    parser = argparse.ArgumentParser(description="阶段2: 切块")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    settings = get_settings()
    sqlite = SQLiteRepo(settings.zvec_data_dir.replace("zvec_db", "app.db"))
    sqlite.init()

    # 查询所有 parsed 状态的论文
    paper_ids = list_papers_by_stage(sqlite, "parsed")
    if args.limit > 0:
        paper_ids = paper_ids[:args.limit]

    print(f"阶段2: 找到 {len(paper_ids)} 篇待切块")

    t0 = time.time()
    results = [stage2_chunk_one(pid, sqlite) for pid in paper_ids]

    ok = sum(1 for r in results if r["status"] == "ok")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    failed = sum(1 for r in results if r["status"] == "failed")
    total_chunks = sum(r.get("chunks", 0) for r in results if r["status"] == "ok")

    print(f"\n{'='*50}")
    print(f"阶段2 完成: {ok} 成功, {skipped} 跳过, {failed} 失败")
    print(f"总 chunks: {total_chunks}")
    print(f"耗时: {time.time()-t0:.1f}s")

    if failed:
        print(f"\n失败论文:")
        for r in results:
            if r["status"] == "failed":
                print(f"  {r['paper_id'][:8]}: {r.get('error', '')[:100]}")


if __name__ == "__main__":
    main()
