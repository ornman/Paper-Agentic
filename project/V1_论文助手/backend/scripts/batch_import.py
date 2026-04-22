"""批量导入测试论文到 Zvec + BM25 + SQLite

用法:
    uv run python scripts/batch_import.py [--concurrency 10] [--skip-existing] [--retries 3]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.pipelines.ingestion.cleaner import clean_markdown
from app.pipelines.ingestion.chunker import chunk_text
from app.pipelines.ingestion.image_handler import inject_image_descriptions
from app.pipelines.ingestion.service import _hash_file
from app.clients.mineru_client import MinerUClient
from app.clients.vlm_client import VLMClient
from app.clients.embedding_client import EmbeddingClient
from app.stores.zvec_store import ZvecStore
from app.stores.bm25_store import BM25Store
from app.stores.sqlite_repo import SQLiteRepo
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("batch_import")


async def import_one(
    file_path: str,
    mineru: MinerUClient,
    vlm: VLMClient,
    embedding: EmbeddingClient,
    zvec: ZvecStore,
    bm25: BM25Store,
    sqlite: SQLiteRepo,
    semaphore: asyncio.Semaphore,
    max_retries: int = 3,
    force_rebuild: bool = False,
    vlm_concurrency: int = 2,
) -> dict:
    """导入单篇论文的完整流程（内置去重 + 自动重试）"""
    basename = os.path.basename(file_path)

    async with semaphore:
        file_hash = _hash_file(file_path)

        # 去重检查（force_rebuild 模式下复用旧 paper_id）
        if not force_rebuild:
            with sqlite.get_session() as session:
                row = session.execute(
                    text("SELECT paper_id FROM papers WHERE file_hash = :hash"),
                    {"hash": file_hash},
                ).fetchone()
                if row:
                    return {"status": "skipped", "file": basename, "reason": "already imported"}

            paper_id = os.urandom(8).hex()
        else:
            # force_rebuild 模式：复用旧 paper_id 或生成新的
            with sqlite.get_session() as session:
                row = session.execute(
                    text("SELECT paper_id FROM papers WHERE file_hash = :hash"),
                    {"hash": file_hash},
                ).fetchone()
                if row:
                    paper_id = row[0]
                    # 清理旧数据
                    zvec.delete_paper(paper_id)
                    bm25.delete_paper(paper_id)
                    logger.info("↻ 清理旧数据: %s", paper_id[:8])
                else:
                    paper_id = os.urandom(8).hex()

        for attempt in range(1, max_retries + 1):
            try:
                return await _do_import(
                    file_path, basename, paper_id, file_hash,
                    mineru, vlm, embedding, zvec, bm25, sqlite,
                    vlm_concurrency,
                )
            except Exception as e:
                if attempt < max_retries and _is_retryable(e):
                    wait = attempt * 3
                    logger.warning("↻ %s 第 %d 次失败，%ds 后重试: %s", basename, attempt, wait, e)
                    await asyncio.sleep(wait)
                else:
                    logger.error("✗ %s → %s", basename, e)
                    return {"status": "failed", "file": basename, "error": str(e)}


def _is_retryable(e: Exception) -> bool:
    """判断错误是否值得重试"""
    msg = str(e).lower()
    retryable = [
        "timeout", "timed out",
        "connection", "remoteprotocol",
        "502", "503", "504", "429",
        "rate limit",
    ]
    return any(kw in msg for kw in retryable)


async def _do_import(
    file_path: str,
    basename: str,
    paper_id: str,
    file_hash: str,
    mineru: MinerUClient,
    vlm: VLMClient,
    embedding: EmbeddingClient,
    zvec: ZvecStore,
    bm25: BM25Store,
    sqlite: SQLiteRepo,
    vlm_concurrency: int = 2,
) -> dict:
    """实际导入逻辑（被 import_one 调用，失败由上层重试）"""

    # 1. MinerU 解析
    result = await mineru.run(file_path)
    md_content = result.md_content or ""
    paper_dir = result.paper_dir
    images_dir = os.path.join(paper_dir, "images")

    # 2. VLM 图片描述
    if md_content and os.path.isdir(images_dir):
        md_content = await inject_image_descriptions(
            md_content, images_dir, paper_dir, vlm, concurrency=vlm_concurrency,
        )

    # 3. 清洗
    chunks = clean_markdown(md_content, paper_id)
    if not chunks:
        return {"status": "empty", "file": basename}

    # 4. 切块
    chunked = chunk_text(chunks)
    if not chunked:
        return {"status": "empty", "file": basename}

    # 5. Embedding
    texts = [c["content"] for c in chunked]
    vectors = await embedding.embed(texts)

    # 6. 存储
    zvec.insert_chunks(
        paper_id,
        [{**c, "file_hash": file_hash} for c in chunked],
        vectors,
    )
    doc_ids = [f"{paper_id}_{i}" for i in range(len(chunked))]
    bm25.add_documents(doc_ids, texts)

    # 推测标题
    title = basename
    if md_content:
        m = re.search(r"^#\s+(.+)$", md_content, re.MULTILINE)
        if m:
            title = m.group(1).strip()

    with sqlite.get_session() as session:
        session.execute(text("""
            INSERT INTO papers (paper_id, title, authors, file_path, file_hash,
                file_size, chunk_count, import_time, status)
            VALUES (:pid, :title, '', :path, :hash, :size, :chunks, :time, 'completed')
        """), {
            "pid": paper_id, "title": title, "path": file_path,
            "hash": file_hash, "size": os.path.getsize(file_path),
            "chunks": len(chunked), "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })
        session.commit()

    logger.info("✓ %s → %d chunks", basename, len(chunked))
    return {"status": "ok", "file": basename, "paper_id": paper_id, "chunks": len(chunked)}


async def main():
    parser = argparse.ArgumentParser(description="批量导入测试论文")
    parser.add_argument("--dir", default="../test_meta_papers", help="论文目录")
    parser.add_argument("--concurrency", type=int, default=5, help="并发数（建议 ≤5，匹配 MinerU 300/min 限流）")
    parser.add_argument("--vlm-concurrency", type=int, default=2, help="VLM 图片描述并发数（建议 2-3）")
    parser.add_argument("--skip-existing", action="store_true", help="跳过已导入的文件")
    parser.add_argument("--force-rebuild", action="store_true", help="强制重建向量库（忽略 file_hash 去重）")
    parser.add_argument("--retries", type=int, default=3, help="单篇失败重试次数")
    parser.add_argument("--limit", type=int, default=0, help="最多导入 N 篇（0=全部）")
    args = parser.parse_args()

    settings = get_settings()

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

    print(f"找到 {len(pdfs)} 篇 PDF，并发 {args.concurrency}，重试 {args.retries} 次")

    # 初始化
    sqlite = SQLiteRepo(settings.zvec_data_dir.replace("zvec_db", "app.db"))
    sqlite.init()
    zvec = ZvecStore(settings.zvec_data_dir, settings.embedding_dimensions)
    zvec.init()
    bm25 = BM25Store(settings.zvec_data_dir.replace("zvec_db", "bm25_index"))
    bm25.init()

    mineru = MinerUClient()
    vlm = VLMClient()
    embed = EmbeddingClient()

    sem = asyncio.Semaphore(args.concurrency)

    # 并发导入
    t0 = time.time()
    tasks = [
        import_one(p, mineru, vlm, embed, zvec, bm25, sqlite, sem,
                   args.retries, args.force_rebuild, args.vlm_concurrency)
        for p in pdfs
    ]
    results = await asyncio.gather(*tasks)

    # 统计
    ok = sum(1 for r in results if r["status"] == "ok")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    failed = sum(1 for r in results if r["status"] == "failed")
    empty = sum(1 for r in results if r["status"] == "empty")
    total_chunks = sum(r.get("chunks", 0) for r in results if r["status"] == "ok")

    print(f"\n{'='*50}")
    print(f"完成: {ok} 成功, {skipped} 跳过, {empty} 空内容, {failed} 失败")
    print(f"总 chunks: {total_chunks}")
    print(f"Zvec: {zvec.stats['doc_count']} docs")
    print(f"BM25: {bm25.doc_count} docs")
    print(f"耗时: {time.time()-t0:.1f}s")

    if failed:
        print(f"\n{'='*50}")
        print(f"失败论文详情 ({failed} 篇):")
        print(f"{'='*50}")
        for r in results:
            if r["status"] == "failed":
                err = r.get("error", "")
                if "429" in err:
                    tag = "429限流"
                elif "timeout" in err.lower() or "timed out" in err.lower():
                    tag = "超时"
                elif "connection" in err.lower():
                    tag = "连接错误"
                else:
                    tag = "服务端错误"
                print(f"  [{tag}] {r['file']}")
                print(f"           {err[:120]}")

    zvec.close()
    await mineru.close()
    await vlm.close()
    await embed.close()


if __name__ == "__main__":
    asyncio.run(main())
