"""批量导入脚本（基于新 LibraryUseCases 骨架）

用法:
    uv run python scripts/batch_import.py [--dir /path/to/pdfs] [--concurrency 3] [--limit 0]
    uv run python scripts/batch_import.py --resume

测试 PDF 不纳入版本控制，请自备数据并指定目录。
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
# 优先使用环境变量，其次回退到 datasets/ 目录
DEFAULT_DATASET_DIR = Path(os.environ.get("BATCH_IMPORT_DIR", str(REPO_ROOT / "datasets")))
sys.path.insert(0, str(BACKEND_ROOT))

from app.bootstrap.container import AppContainer
from app.bootstrap.settings import BackendSettings, get_settings
from app.domain.shared.errors import ConflictError, ValidationError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(message)s",
)
logger = logging.getLogger("batch_import")


def collect_pdfs(pdf_dir: Path, limit: int = 0) -> list[Path]:
    pdfs = sorted(path for path in pdf_dir.rglob("*.pdf") if path.is_file())
    return pdfs[:limit] if limit > 0 else pdfs


async def import_one(
    file_path: Path,
    container: AppContainer,
    sem: asyncio.Semaphore,
    index: int,
    total: int,
    resume: bool,
) -> dict:
    async with sem:
        basename = file_path.name
        normalized_path = str(file_path.resolve())
        logger.info("[%d/%d] 开始导入: %s", index + 1, total, basename)
        started_at = time.time()

        try:
            task = container.library.start_import(normalized_path)
        except ConflictError as exc:
            elapsed = time.time() - started_at
            status = "skipped" if resume else "failed"
            log_fn = logger.info if resume else logger.warning
            log_fn("[%d/%d] %s: %s (%.1fs)", index + 1, total, "跳过(已导入)" if resume else "失败", basename, elapsed)
            return {"file": normalized_path, "status": status, "error": str(exc)}
        except ValidationError as exc:
            elapsed = time.time() - started_at
            logger.warning("[%d/%d] 失败: %s (%.1fs) - %s", index + 1, total, basename, elapsed, exc)
            return {"file": normalized_path, "status": "failed", "error": str(exc)}

        try:
            completed_task = await container.library.run_import(task.task_id)
            elapsed = time.time() - started_at
            library_item = container.library_repo.get(completed_task.library_item_id or "")
            chunk_count = library_item.chunk_count if library_item is not None else 0
            logger.info("[%d/%d] 完成: %s (%.1fs, %d chunks)", index + 1, total, basename, elapsed, chunk_count)
            return {
                "file": normalized_path,
                "status": "ok",
                "task_id": completed_task.task_id,
                "library_item_id": completed_task.library_item_id,
                "chunk_count": chunk_count,
            }
        except Exception as exc:  # pragma: no cover - 真实错误透传给汇总输出
            elapsed = time.time() - started_at
            logger.error("[%d/%d] 异常: %s (%.1fs) - %s", index + 1, total, basename, elapsed, exc)
            return {"file": normalized_path, "status": "failed", "error": str(exc)}


async def main() -> None:
    parser = argparse.ArgumentParser(description="批量导入 Library Item（本地 PDF 路径模式）")
    parser.add_argument("--dir", default=str(DEFAULT_DATASET_DIR), help="PDF 目录")
    parser.add_argument("--concurrency", type=int, default=3, help="并发数")
    parser.add_argument("--limit", type=int, default=0, help="限制导入数量（0=全部）")
    parser.add_argument("--resume", action="store_true", help="跳过已导入的 Library Item")
    args = parser.parse_args()

    pdf_dir = Path(args.dir).expanduser().resolve()
    if not pdf_dir.exists() or not pdf_dir.is_dir():
        raise SystemExit(f"目录不存在: {pdf_dir}")

    settings: BackendSettings = get_settings()
    container = AppContainer(settings)
    await container.initialize()
    try:
        pdfs = collect_pdfs(pdf_dir, args.limit)
        print(f"\n找到 {len(pdfs)} 个 PDF 文件（并发 {args.concurrency}）")
        if not pdfs:
            print("没有需要导入的论文")
            return

        started_at = time.time()
        sem = asyncio.Semaphore(args.concurrency)
        tasks = [import_one(pdf, container, sem, index, len(pdfs), args.resume) for index, pdf in enumerate(pdfs)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        ok = sum(1 for result in results if isinstance(result, dict) and result["status"] == "ok")
        skipped = sum(1 for result in results if isinstance(result, dict) and result["status"] == "skipped")
        failed = sum(1 for result in results if isinstance(result, dict) and result["status"] == "failed")
        errors = sum(1 for result in results if isinstance(result, Exception))
        total_chunks = sum(
            result.get("chunk_count", 0)
            for result in results
            if isinstance(result, dict) and result["status"] == "ok"
        )

        print(f"\n{'=' * 60}")
        print(f"导入完成 (耗时 {time.time() - started_at:.1f}s):")
        print(f"  成功:  {ok}")
        print(f"  跳过:  {skipped}")
        print(f"  失败:  {failed}")
        print(f"  异常:  {errors}")
        print(f"  总 chunks: {total_chunks}")

        failed_items = [result for result in results if isinstance(result, dict) and result["status"] == "failed"]
        if failed_items:
            print(f"\n失败论文 ({len(failed_items)} 篇):")
            for item in failed_items:
                print(f"  {Path(item['file']).name}: {item.get('error', '')[:160]}")

        health = container.health()
        sqlite_info = health["components"]["sqlite"]
        chroma_info = health["components"]["chroma"]
        bm25_info = health["components"]["bm25"]
        print("\n存储状态:")
        print(f"  SQLite library_items: {sqlite_info.get('library_item_count', 0)}")
        print(f"  Chroma chunks: {chroma_info.get('doc_count', 0)}")
        print(f"  BM25 docs: {bm25_info.get('doc_count', 0)}")
        print(f"  Redis: {health['components']['redis']['status']}")
    finally:
        await container.close()


if __name__ == "__main__":
    asyncio.run(main())
