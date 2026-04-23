"""阶段3：从 chunks JSON → Embedding → 存储到 Zvec + BM25 + SQLite

用法:
    uv run python scripts/stage3_vectorize.py [--concurrency 10]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.clients.embedding_client import EmbeddingClient
from app.stores.zvec_store import ZvecStore
from app.stores.bm25_store import BM25Store
from app.stores.sqlite_repo import SQLiteRepo
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("stage3_vectorize")

CHUNKS_DIR = "./data/chunks"


async def stage3_vectorize_one(
    paper_id: str,
    embedding: EmbeddingClient,
    zvec: ZvecStore,
    bm25: BM25Store,
    sqlite: SQLiteRepo,
    semaphore: asyncio.Semaphore,
    max_retries: int = 3,
) -> dict:
    """单篇论文向量化 + 存储"""

    async with semaphore:
        # 读取 chunks JSON
        chunks_path = os.path.join(CHUNKS_DIR, f"{paper_id}.json")
        if not os.path.exists(chunks_path):
            logger.warning("chunks JSON 不存在: %s", paper_id[:8])
            return {"status": "skipped", "paper_id": paper_id, "reason": "no chunks file"}

        with open(chunks_path, "r", encoding="utf-8") as f:
            chunked_data = json.load(f)

        chunks = chunked_data["chunks"]
        file_hash = chunked_data.get("file_hash", "")
        title = chunked_data.get("title", paper_id[:8])
        file_path = chunked_data.get("file_path", "")

        if not chunks:
            _update_stage(sqlite, paper_id, "failed", "chunks 为空")
            return {"status": "failed", "paper_id": paper_id, "error": "chunks 为空"}

        for attempt in range(1, max_retries + 1):
            try:
                return await _do_vectorize(
                    paper_id, chunks, file_hash, title, file_path,
                    embedding, zvec, bm25, sqlite,
                )
            except Exception as e:
                if attempt < max_retries and _is_retryable(e):
                    wait = attempt * 3
                    logger.warning("%s 第 %d 次失败，%ds 后重试: %s", paper_id[:8], attempt, wait, e)
                    await asyncio.sleep(wait)
                else:
                    logger.error("X %s: %s", paper_id[:8], e)
                    _update_stage(sqlite, paper_id, "failed", str(e))
                    return {"status": "failed", "paper_id": paper_id, "error": str(e)}


async def _do_vectorize(
    paper_id: str,
    chunks: list[dict],
    file_hash: str,
    title: str,
    file_path: str,
    embedding: EmbeddingClient,
    zvec: ZvecStore,
    bm25: BM25Store,
    sqlite: SQLiteRepo,
) -> dict:
    """实际向量化逻辑"""
    texts = [c["content"] for c in chunks]

    # 1. Embedding
    vectors = await embedding.embed(texts)

    # 2. 存储到 Zvec
    enriched_chunks = [{**c, "file_hash": file_hash} for c in chunks]
    stored = zvec.insert_chunks(paper_id, enriched_chunks, vectors)

    # 3. 存储到 BM25
    doc_ids = [f"{paper_id}_{i}" for i in range(len(chunks))]
    bm25.add_documents(doc_ids, texts)

    # 4. 存储到 SQLite papers 表
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    with sqlite.get_session() as session:
        session.execute(text("""
            INSERT OR REPLACE INTO papers (paper_id, title, authors, file_path, file_hash,
                chunk_count, import_time, status)
            VALUES (:pid, :title, '', :path, :hash, :chunks, :time, 'completed')
        """), {
            "pid": paper_id, "title": title, "path": file_path,
            "hash": file_hash, "chunks": stored, "time": now,
        })
        session.commit()

    # 5. 更新 import_progress 状态
    _update_stage(sqlite, paper_id, "completed")

    # 6. 清理 chunks JSON
    chunks_path = os.path.join(CHUNKS_DIR, f"{paper_id}.json")
    if os.path.exists(chunks_path):
        os.remove(chunks_path)

    logger.info("O %s → %d vectors", paper_id[:8], stored)
    return {"status": "ok", "paper_id": paper_id, "chunks": stored}


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


def _is_retryable(e: Exception) -> bool:
    msg = str(e).lower()
    return any(kw in msg for kw in ["timeout", "timed out", "connection", "502", "503", "504", "429", "rate limit"])


def list_papers_by_stage(sqlite: SQLiteRepo, stage: str) -> list[str]:
    with sqlite.get_session() as session:
        rows = session.execute(
            text("SELECT paper_id FROM import_progress WHERE stage = :stage"),
            {"stage": stage},
        ).fetchall()
        return [row[0] for row in rows]


async def main():
    parser = argparse.ArgumentParser(description="阶段3: 向量化 + 存储")
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    settings = get_settings()

    sqlite = SQLiteRepo(settings.zvec_data_dir.replace("zvec_db", "app.db"))
    sqlite.init()
    zvec = ZvecStore(settings.zvec_data_dir, settings.embedding_dimensions)
    zvec.init()
    bm25 = BM25Store(settings.zvec_data_dir.replace("zvec_db", "bm25_index"))
    bm25.init()
    embedding = EmbeddingClient()

    # 查询所有 chunked 状态的论文
    paper_ids = list_papers_by_stage(sqlite, "chunked")
    if args.limit > 0:
        paper_ids = paper_ids[:args.limit]

    print(f"阶段3: 找到 {len(paper_ids)} 篇待向量化")

    sem = asyncio.Semaphore(args.concurrency)
    t0 = time.time()

    tasks = [
        stage3_vectorize_one(pid, embedding, zvec, bm25, sqlite, sem, args.retries)
        for pid in paper_ids
    ]
    results = await asyncio.gather(*tasks)

    ok = sum(1 for r in results if r["status"] == "ok")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    failed = sum(1 for r in results if r["status"] == "failed")
    total_vectors = sum(r.get("chunks", 0) for r in results if r["status"] == "ok")

    print(f"\n{'='*50}")
    print(f"阶段3 完成: {ok} 成功, {skipped} 跳过, {failed} 失败")
    print(f"总 vectors: {total_vectors}")
    print(f"Zvec: {zvec.stats['doc_count']} docs")
    print(f"BM25: {bm25.doc_count} docs")
    print(f"耗时: {time.time()-t0:.1f}s")

    if failed:
        print(f"\n失败论文:")
        for r in results:
            if r["status"] == "failed":
                print(f"  {r['paper_id'][:8]}: {r.get('error', '')[:100]}")

    zvec.close()
    await embedding.close()


if __name__ == "__main__":
    asyncio.run(main())
