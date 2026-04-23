"""阶段1：MinerU 解析 + VLM 图片描述 + 清洗 → 保存到 data/parsed/{paper_id}.json

用法:
    uv run python scripts/stage1_parse.py [--dir ../test_meta_papers] [--concurrency 5]
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.clients.mineru_client import MinerUClient
from app.clients.vlm_client import VLMClient
from app.pipelines.ingestion.cleaner import clean_markdown
from app.pipelines.ingestion.image_handler import inject_image_descriptions
from app.stores.sqlite_repo import SQLiteRepo
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("stage1_parse")

PARSED_DIR = "./data/parsed"


def hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()


def guess_title(md_content: str | None, file_path: str) -> str:
    if md_content:
        m = re.search(r"^#\s+(.+)$", md_content, re.MULTILINE)
        if m:
            return m.group(1).strip()
    return os.path.splitext(os.path.basename(file_path))[0]


async def stage1_parse_one(
    file_path: str,
    mineru: MinerUClient,
    vlm: VLMClient,
    sqlite: SQLiteRepo,
    semaphore: asyncio.Semaphore,
    max_retries: int = 3,
) -> dict:
    """解析单篇 PDF → 保存 parsed JSON"""
    basename = os.path.basename(file_path)

    async with semaphore:
        file_hash = hash_file(file_path)

        # 查已有进度
        with sqlite.get_session() as session:
            row = session.execute(
                text("SELECT paper_id, stage FROM import_progress WHERE file_hash = :hash"),
                {"hash": file_hash},
            ).fetchone()

            if row and row[1] in ("parsed", "chunked", "completed"):
                logger.info("跳过 (已到阶段 %s): %s", row[1], basename)
                return {"status": "skipped", "file": basename, "stage": row[1]}

            paper_id = row[0] if row else os.urandom(8).hex()

        # parsed JSON 已存在但 DB 没记录 → 也跳过
        parsed_path = os.path.join(PARSED_DIR, f"{paper_id}.json")
        if os.path.exists(parsed_path):
            logger.info("跳过 (parsed JSON 存在): %s", basename)
            _update_stage(sqlite, paper_id, file_path, file_hash, "parsed")
            return {"status": "skipped", "file": basename, "stage": "parsed"}

        # 重试逻辑
        for attempt in range(1, max_retries + 1):
            try:
                result = await _do_parse(file_path, basename, paper_id, file_hash, mineru, vlm, sqlite)
                return result
            except Exception as e:
                if attempt < max_retries and _is_retryable(e):
                    wait = attempt * 3
                    logger.warning("%s 第 %d 次失败，%ds 后重试: %s", basename, attempt, wait, e)
                    await asyncio.sleep(wait)
                else:
                    logger.error("X %s: %s", basename, e)
                    _update_stage(sqlite, paper_id, file_path, file_hash, "failed", str(e))
                    return {"status": "failed", "file": basename, "error": str(e)}


async def _do_parse(
    file_path: str,
    basename: str,
    paper_id: str,
    file_hash: str,
    mineru: MinerUClient,
    vlm: VLMClient,
    sqlite: SQLiteRepo,
) -> dict:
    """实际解析逻辑"""
    # 1. MinerU 解析
    result = await mineru.run(file_path)
    md_content = result.md_content or ""
    paper_dir = result.paper_dir

    if not md_content:
        _update_stage(sqlite, paper_id, file_path, file_hash, "failed", "MinerU 无内容")
        return {"status": "failed", "file": basename, "error": "MinerU 无内容"}

    # 2. VLM 图片描述（容错：失败不阻塞）
    images_dir = os.path.join(paper_dir, "images")
    if os.path.isdir(images_dir):
        try:
            md_content = await inject_image_descriptions(
                md_content, images_dir, paper_dir, vlm, concurrency=2,
            )
        except Exception as e:
            logger.warning("VLM 描述失败，跳过: %s → %s", basename, e)

    # 3. 清洗
    chunks = clean_markdown(md_content, paper_id)
    if not chunks:
        _update_stage(sqlite, paper_id, file_path, file_hash, "failed", "清洗后为空")
        return {"status": "failed", "file": basename, "error": "清洗后为空"}

    # 4. 保存 parsed JSON
    os.makedirs(PARSED_DIR, exist_ok=True)
    parsed_data = {
        "paper_id": paper_id,
        "file_path": file_path,
        "file_hash": file_hash,
        "title": guess_title(md_content, file_path),
        "chunks": [
            {
                "chunk_id": c.chunk_id,
                "content": c.content,
                "page": c.page,
                "chunk_type": c.chunk_type,
                "section_title": c.section_title,
                "section_level": c.section_level,
                "has_image": c.has_image,
            }
            for c in chunks
        ],
        "mineru_task_id": result.task_id,
        "paper_dir": paper_dir,
    }

    parsed_path = os.path.join(PARSED_DIR, f"{paper_id}.json")
    with open(parsed_path, "w", encoding="utf-8") as f:
        json.dump(parsed_data, f, ensure_ascii=False, indent=2)

    # 5. 更新状态
    _update_stage(sqlite, paper_id, file_path, file_hash, "parsed")

    logger.info("O %s → %d 语义块", basename, len(chunks))
    return {"status": "ok", "file": basename, "paper_id": paper_id, "chunks": len(chunks)}


def _update_stage(
    sqlite: SQLiteRepo,
    paper_id: str,
    file_path: str,
    file_hash: str,
    stage: str,
    error_msg: str | None = None,
) -> None:
    """更新 import_progress 表"""
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    with sqlite.get_session() as session:
        session.execute(text("""
            INSERT INTO import_progress (paper_id, file_path, file_hash, stage, error_msg, updated_at)
            VALUES (:pid, :path, :hash, :stage, :err, :time)
            ON CONFLICT(file_hash) DO UPDATE SET
                stage = :stage, error_msg = :err, updated_at = :time
        """), {
            "pid": paper_id, "path": file_path, "hash": file_hash,
            "stage": stage, "err": error_msg, "time": now,
        })
        session.commit()


def _is_retryable(e: Exception) -> bool:
    msg = str(e).lower()
    return any(kw in msg for kw in ["timeout", "timed out", "connection", "502", "503", "504", "429", "rate limit"])


async def main():
    parser = argparse.ArgumentParser(description="阶段1: MinerU 解析 + VLM + 清洗")
    parser.add_argument("--dir", default="../test_meta_papers", help="PDF 目录")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    settings = get_settings()
    sqlite = SQLiteRepo(settings.zvec_data_dir.replace("zvec_db", "app.db"))
    sqlite.init()
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

    print(f"阶段1: 找到 {len(pdfs)} 篇 PDF，并发 {args.concurrency}")

    sem = asyncio.Semaphore(args.concurrency)
    t0 = time.time()

    tasks = [
        stage1_parse_one(p, mineru, vlm, sqlite, sem, args.retries)
        for p in pdfs
    ]
    results = await asyncio.gather(*tasks)

    ok = sum(1 for r in results if r["status"] == "ok")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    failed = sum(1 for r in results if r["status"] == "failed")
    total_chunks = sum(r.get("chunks", 0) for r in results if r["status"] == "ok")

    print(f"\n{'='*50}")
    print(f"阶段1 完成: {ok} 成功, {skipped} 跳过, {failed} 失败")
    print(f"总语义块: {total_chunks}")
    print(f"耗时: {time.time()-t0:.1f}s")

    if failed:
        print(f"\n失败论文:")
        for r in results:
            if r["status"] == "failed":
                print(f"  {r['file']}: {r.get('error', '')[:100]}")

    await mineru.close()
    await vlm.close()


if __name__ == "__main__":
    asyncio.run(main())
