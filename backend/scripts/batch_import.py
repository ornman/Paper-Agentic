"""批量导入脚本（基于 IngestionService + BackupManager）

用法:
    uv run python scripts/batch_import.py [--dir ../datasets/test_meta_papers] [--concurrency 3] [--limit 0]
    uv run python scripts/batch_import.py --resume   # 断点续传：跳过已完成的论文
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
from app.stores.chroma_store import ChromaStore
from app.stores.bm25_store import BM25Store
from app.stores.sqlite_repo import SQLiteRepo
from app.api.v1.deps import init_deps
from app.pipelines.ingestion.service import IngestionService
from app.pipelines.ingestion.backup_manager import BackupManager
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(message)s",
)
logger = logging.getLogger("batch_import")


def collect_pdfs(pdf_dir: str, limit: int = 0) -> list[str]:
    """递归收集目录下所有 PDF 文件"""
    pdfs = []
    for root, _, files in os.walk(pdf_dir):
        for f in sorted(files):
            if f.lower().endswith(".pdf"):
                pdfs.append(os.path.join(root, f))
    pdfs.sort()
    if limit > 0:
        pdfs = pdfs[:limit]
    return pdfs


def get_completed_hashes(backup: BackupManager) -> set[str]:
    """获取备份中已完成的 file_hash 集合"""
    completed = set()
    backup_dir = backup._backup_dir
    if not os.path.isdir(backup_dir):
        return completed

    for name in os.listdir(backup_dir):
        manifest_path = os.path.join(backup_dir, name, "backup.json")
        if not os.path.exists(manifest_path):
            continue
        import json
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("status") == "completed":
            completed.add(name)
    return completed


async def import_one(
    file_path: str,
    service: IngestionService,
    sem: asyncio.Semaphore,
    index: int,
    total: int,
) -> dict:
    """导入单个 PDF"""
    async with sem:
        basename = os.path.basename(file_path)
        logger.info("[%d/%d] 开始导入: %s", index + 1, total, basename)
        t0 = time.time()

        try:
            result = await service.ingest_pdf(file_path)
            elapsed = time.time() - t0
            logger.info("[%d/%d] 完成: %s (%.1fs, %d chunks)",
                        index + 1, total, basename, elapsed, result.get("chunk_count", 0))
            return {"file": file_path, "status": "ok", "result": result}
        except ValueError as e:
            elapsed = time.time() - t0
            msg = str(e)
            if "已导入" in msg or "已完成" in msg:
                logger.info("[%d/%d] 跳过(已导入): %s", index + 1, total, basename)
                return {"file": file_path, "status": "skipped", "error": msg}
            logger.warning("[%d/%d] 失败: %s (%.1fs) - %s", index + 1, total, basename, elapsed, msg)
            return {"file": file_path, "status": "failed", "error": msg}
        except Exception as e:
            elapsed = time.time() - t0
            logger.error("[%d/%d] 异常: %s (%.1fs) - %s", index + 1, total, basename, elapsed, e)
            return {"file": file_path, "status": "failed", "error": str(e)}


async def main():
    parser = argparse.ArgumentParser(description="批量导入论文（ChromaDB + 备份断点续传）")
    parser.add_argument("--dir", default="../datasets/test_meta_papers", help="PDF 目录")
    parser.add_argument("--concurrency", type=int, default=3, help="并发数")
    parser.add_argument("--limit", type=int, default=0, help="限制导入数量（0=全部）")
    parser.add_argument("--resume", action="store_true", help="断点续传：跳过已完成的论文")
    args = parser.parse_args()

    settings = get_settings()

    # 初始化存储层
    sqlite = SQLiteRepo("./data/app.db")
    sqlite.init()

    chroma = ChromaStore(settings.chroma_data_dir, settings.embedding_dimensions)
    chroma.init()

    bm25 = BM25Store("./data/bm25_index")
    bm25.init()

    init_deps(sqlite=sqlite, chroma=chroma, bm25=bm25)

    # 收集 PDF
    pdf_dir = os.path.abspath(args.dir)
    pdfs = collect_pdfs(pdf_dir, args.limit)
    print(f"\n找到 {len(pdfs)} 个 PDF 文件（并发 {args.concurrency}）")

    # 断点续传：过滤已完成的
    if args.resume:
        backup = BackupManager(settings.backup_dir)
        completed_hashes = get_completed_hashes(backup)
        if completed_hashes:
            # 计算 file_hash 来过滤
            import hashlib
            remaining = []
            for p in pdfs:
                h = hashlib.sha256()
                with open(p, "rb") as f:
                    for block in iter(lambda: f.read(8192), b""):
                        h.update(block)
                if h.hexdigest() not in completed_hashes:
                    remaining.append(p)
            skipped = len(pdfs) - len(remaining)
            print(f"断点续传: 跳过 {skipped} 篇已完成，剩余 {len(remaining)} 篇")
            pdfs = remaining

    if not pdfs:
        print("没有需要导入的论文")
        return

    # 执行导入
    service = IngestionService()
    sem = asyncio.Semaphore(args.concurrency)

    t0 = time.time()
    tasks = [import_one(p, service, sem, i, len(pdfs)) for i, p in enumerate(pdfs)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 统计
    ok = sum(1 for r in results if isinstance(r, dict) and r["status"] == "ok")
    skipped = sum(1 for r in results if isinstance(r, dict) and r["status"] == "skipped")
    failed = sum(1 for r in results if isinstance(r, dict) and r["status"] == "failed")
    errors = sum(1 for r in results if isinstance(r, Exception))

    total_chunks = sum(
        r["result"].get("chunk_count", 0)
        for r in results
        if isinstance(r, dict) and r["status"] == "ok"
    )

    print(f"\n{'='*60}")
    print(f"导入完成 (耗时 {time.time()-t0:.1f}s):")
    print(f"  成功:  {ok}")
    print(f"  跳过:  {skipped}")
    print(f"  失败:  {failed}")
    print(f"  异常:  {errors}")
    print(f"  总 chunks: {total_chunks}")

    # 打印失败列表
    failed_items = [
        r for r in results
        if isinstance(r, dict) and r["status"] == "failed"
    ]
    if failed_items:
        print(f"\n失败论文 ({len(failed_items)} 篇):")
        for item in failed_items:
            print(f"  {os.path.basename(item['file'])}: {item.get('error', '')[:100]}")
        print(f"\n重试命令:")
        print(f"  uv run python scripts/batch_import.py --resume --dir \"{pdf_dir}\"")

    # 打印当前存储统计
    chroma_stats = chroma.stats
    print(f"\n存储状态:")
    print(f"  ChromaDB: {chroma_stats['doc_count']} docs")
    print(f"  SQLite papers: {sqlite.get_paper_count()}")

    await service.close()
    chroma.close()


if __name__ == "__main__":
    asyncio.run(main())
