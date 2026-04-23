"""三阶段批量导入主控

编排 stage1(解析) → stage2(切块) → stage3(向量化)，支持断点续传。

用法:
    uv run python scripts/batch_import_v2.py [--dir ../test_meta_papers] [--concurrency 5]
    uv run python scripts/batch_import_v2.py --resume   # 断点续传：从上次中断处继续
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.clients.mineru_client import MinerUClient
from app.clients.vlm_client import VLMClient
from app.clients.embedding_client import EmbeddingClient
from app.stores.zvec_store import ZvecStore
from app.stores.bm25_store import BM25Store
from app.stores.sqlite_repo import SQLiteRepo
from sqlalchemy import text

from scripts.stage1_parse import stage1_parse_one, PARSED_DIR
from scripts.stage2_chunk import stage2_chunk_one, CHUNKS_DIR
from scripts.stage3_vectorize import stage3_vectorize_one

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("batch_import_v2")


def list_papers_by_stage(sqlite: SQLiteRepo, stage: str) -> list[str]:
    with sqlite.get_session() as session:
        rows = session.execute(
            text("SELECT paper_id FROM import_progress WHERE stage = :stage"),
            {"stage": stage},
        ).fetchall()
        return [row[0] for row in rows]


async def run_stage1(
    pdf_files: list[str],
    mineru: MinerUClient,
    vlm: VLMClient,
    sqlite: SQLiteRepo,
    concurrency: int,
    retries: int,
) -> list[dict]:
    """阶段1：并发解析所有 PDF"""
    sem = asyncio.Semaphore(concurrency)
    tasks = [
        stage1_parse_one(p, mineru, vlm, sqlite, sem, retries)
        for p in pdf_files
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    parsed = []
    for r in results:
        if isinstance(r, Exception):
            logger.error("阶段1 异常: %s", r)
        elif r["status"] == "ok":
            parsed.append(r)
    return parsed


def run_stage2(
    sqlite: SQLiteRepo,
) -> list[dict]:
    """阶段2：同步切块"""
    paper_ids = list_papers_by_stage(sqlite, "parsed")
    logger.info("阶段2: %d 篇待切块", len(paper_ids))

    results = []
    for pid in paper_ids:
        r = stage2_chunk_one(pid, sqlite)
        results.append(r)
        if isinstance(r, Exception):
            logger.error("阶段2 异常: %s", r)
    return results


async def run_stage3(
    sqlite: SQLiteRepo,
    embedding: EmbeddingClient,
    zvec: ZvecStore,
    bm25: BM25Store,
    concurrency: int,
    retries: int,
) -> list[dict]:
    """阶段3：并发向量化"""
    paper_ids = list_papers_by_stage(sqlite, "chunked")
    logger.info("阶段3: %d 篇待向量化", len(paper_ids))

    sem = asyncio.Semaphore(concurrency)
    tasks = [
        stage3_vectorize_one(pid, embedding, zvec, bm25, sqlite, sem, retries)
        for pid in paper_ids
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    vectorized = []
    for r in results:
        if isinstance(r, Exception):
            logger.error("阶段3 异常: %s", r)
        elif r["status"] == "ok":
            vectorized.append(r)
    return vectorized


async def main():
    parser = argparse.ArgumentParser(description="三阶段批量导入")
    parser.add_argument("--dir", default="../test_meta_papers", help="PDF 目录")
    parser.add_argument("--concurrency", type=int, default=5, help="阶段1/3 并发数")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true", help="断点续传：跳过阶段1/2，从阶段3 继续")
    parser.add_argument("--stage1-only", action="store_true", help="只运行阶段1")
    parser.add_argument("--stage2-only", action="store_true", help="只运行阶段2")
    parser.add_argument("--stage3-only", action="store_true", help="只运行阶段3")
    args = parser.parse_args()

    settings = get_settings()

    # 初始化
    sqlite = SQLiteRepo(settings.zvec_data_dir.replace("zvec_db", "app.db"))
    sqlite.init()

    # 初始化数据目录
    os.makedirs(PARSED_DIR, exist_ok=True)
    os.makedirs(CHUNKS_DIR, exist_ok=True)

    t0 = time.time()

    # ── 阶段1 ──
    if not args.resume and not args.stage2_only and not args.stage3_only:
        mineru = MinerUClient()
        vlm = VLMClient()

        # 收集 PDF
        pdf_dir = os.path.abspath(args.dir)
        pdfs = []
        for root, _, files in os.walk(pdf_dir):
            for f in files:
                if f.lower().endswith(".pdf"):
                    pdfs.append(os.path.join(root, f))
        pdfs.sort()
        if args.limit > 0:
            pdfs = pdfs[:args.limit]

        print(f"\n阶段1: 解析 {len(pdfs)} 篇 PDF（并发 {args.concurrency}）")
        s1_results = await run_stage1(pdfs, mineru, vlm, sqlite, args.concurrency, args.retries)

        s1_ok = sum(1 for r in s1_results if r["status"] == "ok")
        s1_skip = sum(1 for r in s1_results if r["status"] == "skipped")
        s1_fail = sum(1 for r in s1_results if r["status"] == "failed")
        print(f"阶段1 完成: {s1_ok} 成功, {s1_skip} 跳过, {s1_fail} 失败")

        await mineru.close()
        await vlm.close()

        if args.stage1_only:
            _print_summary(sqlite, t0)
            return

    # ── 阶段2 ──
    if not args.resume and not args.stage1_only and not args.stage3_only:
        print(f"\n阶段2: 切块")
        s2_results = run_stage2(sqlite)

        s2_ok = sum(1 for r in s2_results if r["status"] == "ok")
        s2_skip = sum(1 for r in s2_results if r["status"] == "skipped")
        s2_fail = sum(1 for r in s2_results if r["status"] == "failed")
        print(f"阶段2 完成: {s2_ok} 成功, {s2_skip} 跳过, {s2_fail} 失败")

        if args.stage2_only:
            _print_summary(sqlite, t0)
            return

    # ── 阶段3 ──
    if not args.stage1_only and not args.stage2_only:
        zvec = ZvecStore(settings.zvec_data_dir, settings.embedding_dimensions)
        zvec.init()
        bm25 = BM25Store(settings.zvec_data_dir.replace("zvec_db", "bm25_index"))
        bm25.init()
        embedding = EmbeddingClient()

        print(f"\n阶段3: 向量化（并发 {args.concurrency}）")
        s3_results = await run_stage3(sqlite, embedding, zvec, bm25, args.concurrency, args.retries)

        s3_ok = sum(1 for r in s3_results if r["status"] == "ok")
        s3_skip = sum(1 for r in s3_results if r["status"] == "skipped")
        s3_fail = sum(1 for r in s3_results if r["status"] == "failed")
        print(f"阶段3 完成: {s3_ok} 成功, {s3_skip} 跳过, {s3_fail} 失败")

        zvec.close()
        await embedding.close()

    _print_summary(sqlite, t0)


def _print_summary(sqlite: SQLiteRepo, t0: float) -> None:
    """打印最终统计"""
    stages = {}
    for stage in ("parsed", "chunked", "completed", "failed"):
        stages[stage] = len(list_papers_by_stage(sqlite, stage))

    print(f"\n{'='*60}")
    print(f"导入总结 (耗时 {time.time()-t0:.1f}s):")
    print(f"  parsed:   {stages.get('parsed', 0)}")
    print(f"  chunked:  {stages.get('chunked', 0)}")
    print(f"  completed:{stages.get('completed', 0)}")
    print(f"  failed:   {stages.get('failed', 0)}")

    if stages.get("failed", 0) > 0:
        failed_ids = list_papers_by_stage(sqlite, "failed")
        print(f"\n失败论文 ({len(failed_ids)} 篇):")
        with sqlite.get_session() as session:
            for pid in failed_ids:
                row = session.execute(
                    text("SELECT file_path, error_msg FROM import_progress WHERE paper_id = :pid"),
                    {"pid": pid},
                ).fetchone()
                if row:
                    basename = os.path.basename(row[0])
                    print(f"  {basename}: {row[1][:100] if row[1] else ''}")

        print(f"\n重试命令:")
        print(f"  # 1. 查看失败原因")
        print(f"  # 2. 修复后重试阶段1:")
        print(f"  uv run python scripts/batch_import_v2.py --stage1-only --dir <pdf_dir>")
        print(f"  # 3. 或单独重试阶段2/3:")
        print(f"  uv run python scripts/batch_import_v2.py --stage2-only")
        print(f"  uv run python scripts/batch_import_v2.py --stage3-only")


if __name__ == "__main__":
    asyncio.run(main())
