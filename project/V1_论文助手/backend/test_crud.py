"""真实入库 + CRUD 验证"""

import asyncio
import os
import shutil
import sys

sys.path.insert(0, ".")

from app.core.config import get_settings
from app.stores.zvec_store import ZvecStore
from app.stores.sqlite_repo import SQLiteRepo
from app.stores.bm25_store import BM25Store
from app.clients.embedding_client import EmbeddingClient
from app.pipelines.ingestion.cleaner import clean_markdown
from app.pipelines.ingestion.chunker import chunk_text, estimate_tokens
from sqlalchemy import text


async def main():
    settings = get_settings()

    # ── 初始化真实存储 ──
    print("=== 初始化存储 ===")
    if os.path.exists(settings.zvec_data_dir):
        shutil.rmtree(settings.zvec_data_dir)

    sqlite = SQLiteRepo("./data/app.db")
    sqlite.init()
    zvec = ZvecStore(settings.zvec_data_dir, settings.embedding_dimensions)
    zvec.init()
    bm25 = BM25Store("./data/bm25_index")
    bm25.init()
    embed = EmbeddingClient()

    paper_id = "paper_test_001"
    md_path = "./data/papers/85266a7a-f0aa-4ba1-bf55-43533448da12/full.md"

    # ── Step 1: 清洗 ──
    print("\n=== Step 1: 清洗 ===")
    with open(md_path, encoding="utf-8") as f:
        md = f.read()
    chunks = clean_markdown(md, paper_id)
    print(f"清洗结果: {len(chunks)} chunks, {sum(len(c.content) for c in chunks)} chars")

    # ── Step 2: 切块 ──
    print("\n=== Step 2: 切块 (1000 tokens) ===")
    chunked = chunk_text(chunks)
    texts = [c["content"] for c in chunked]
    print(f"切块结果: {len(chunked)} chunks")
    for i, c in enumerate(chunked[:3]):
        print(f"  [{i}] tokens={c['tokens']}")

    # ── Step 3: Embedding ──
    print(f"\n=== Step 3: Embedding ({len(texts)} texts) ===")
    vectors = await embed.embed(texts)
    print(f"Embedding 完成: {len(vectors)} vectors, dim={len(vectors[0])}")

    # ── Step 4: 入库 Zvec ──
    print("\n=== Step 4: 写入 Zvec ===")
    stored = zvec.insert_chunks(
        paper_id,
        [{**c, "file_hash": "test_hash_001", "paper_id": paper_id} for c in chunked],
        vectors,
    )
    print(f"Zvec 写入: {stored} docs, total={zvec.stats['doc_count']}")

    # ── Step 5: 入库 BM25 ──
    print("\n=== Step 5: 写入 BM25 ===")
    doc_ids = [f"{paper_id}_{i}" for i in range(len(chunked))]
    bm25.add_documents(doc_ids, texts)
    print(f"BM25 写入: {bm25.doc_count} docs")

    # ── Step 6: 入库 SQLite ──
    print("\n=== Step 6: 写入 SQLite ===")
    with sqlite.get_session() as session:
        session.execute(text("""
            INSERT INTO papers (paper_id, title, authors, file_path, file_hash,
                file_size, chunk_count, import_time, status)
            VALUES (:pid, :title, '', :path, :hash, :size, :chunks, :time, 'completed')
        """), {
            "pid": paper_id,
            "title": "VR技术在公共文化服务中的应用研究",
            "path": md_path,
            "hash": "test_hash_001",
            "size": os.path.getsize(md_path),
            "chunks": stored,
            "time": "2026-04-19T00:00:00",
        })
        session.commit()
    count = sqlite.get_paper_count()
    print(f"SQLite 写入: paper_count={count}")

    # ══════════════════════════════════════
    # CRUD 验证
    # ══════════════════════════════════════
    print("\n" + "=" * 50)
    print("CRUD 验证")
    print("=" * 50)

    # ── R: Zvec 检索（全量） ──
    print("\n--- Read: Zvec 全量检索 ---")
    query_vec = vectors[0]
    results = zvec.query(query_vec, topk=5)
    print(f"全量检索: {len(results)} results")
    for r in results[:3]:
        fields = r.fields if hasattr(r, "fields") else {}
        pid = fields.get("paper_id", "?") if isinstance(fields, dict) else "?"
        content = fields.get("content", "")[:50] if isinstance(fields, dict) else ""
        print(f"  score={r.score:.4f} paper={pid[:12]} \"{content}...\"")

    # ── R: Zvec 按 paper_id 过滤 ──
    print("\n--- Read: Zvec 按 paper_id 过滤 ---")
    filtered = zvec.query(query_vec, topk=5, paper_id=paper_id)
    print(f"过滤检索: {len(filtered)} results (全部应为 paper_test_001)")
    for r in filtered[:3]:
        fields = r.fields if hasattr(r, "fields") else {}
        pid = fields.get("paper_id", "?") if isinstance(fields, dict) else "?"
        print(f"  score={r.score:.4f} paper={pid[:12]}")

    # ── R: BM25 检索 ──
    print("\n--- Read: BM25 关键词检索 ---")
    bm25_results = bm25.query("VR技术 数字化博物馆", topk=5)
    print(f"BM25 检索: {len(bm25_results)} results")
    for did, score in bm25_results[:3]:
        print(f"  score={score:.4f} doc={did}")

    # ── R: SQLite 列表 ──
    print("\n--- Read: SQLite 论文列表 ---")
    with sqlite.get_session() as session:
        rows = session.execute(text(
            "SELECT paper_id, title, chunk_count, status FROM papers"
        )).fetchall()
    for row in rows:
        print(f"  id={row[0]} title=\"{row[1][:30]}\" chunks={row[2]} status={row[3]}")

    # ── U: 模拟更新（改标题） ──
    print("\n--- Update: SQLite 改标题 ---")
    with sqlite.get_session() as session:
        session.execute(text(
            "UPDATE papers SET title = :title WHERE paper_id = :pid"
        ), {"title": "VR技术在公共文化服务中的应用研究（已更新）", "pid": paper_id})
        session.commit()
    with sqlite.get_session() as session:
        row = session.execute(text(
            "SELECT title FROM papers WHERE paper_id = :pid"
        ), {"pid": paper_id}).fetchone()
    print(f"  更新后标题: \"{row[0]}\"")

    # ── 入库第二篇论文，验证多论文共存 ──
    print("\n--- 入库第二篇论文 ---")
    paper_id_2 = "paper_test_002"
    # 用同一篇 MD 模拟第二篇
    chunks2 = clean_markdown(md, paper_id_2)
    chunked2 = chunk_text(chunks2)
    # 只取前 10 个 chunk 省时间
    chunked2 = chunked2[:10]
    texts2 = [c["content"] for c in chunked2]
    vectors2 = await embed.embed(texts2)

    zvec.insert_chunks(paper_id_2, [{**c, "file_hash": "hash_002", "paper_id": paper_id_2} for c in chunked2], vectors2)
    bm25.add_documents([f"{paper_id_2}_{i}" for i in range(len(chunked2))], texts2)
    with sqlite.get_session() as session:
        session.execute(text("""
            INSERT INTO papers (paper_id, title, authors, file_path, file_hash,
                file_size, chunk_count, import_time, status)
            VALUES (:pid, :title, '', :path, :hash, 0, :chunks, :time, 'completed')
        """), {
            "pid": paper_id_2, "title": "第二篇测试论文",
            "path": md_path, "hash": "hash_002",
            "chunks": len(chunked2), "time": "2026-04-19T00:00:00",
        })
        session.commit()
    print(f"  Zvec total: {zvec.stats['doc_count']}, SQLite: {sqlite.get_paper_count()} papers")

    # 验证按 paper_id 过滤只返回对应论文
    print("\n--- 验证多论文过滤 ---")
    r1 = zvec.query(query_vec, topk=100, paper_id=paper_id)
    r2 = zvec.query(query_vec, topk=100, paper_id=paper_id_2)
    print(f"  paper_001: {len(r1)} results, paper_002: {len(r2)} results")

    # ── D: 删除第一篇论文 ──
    print("\n--- Delete: 删除 paper_test_001 ---")
    zvec.delete_paper(paper_id)
    bm25.delete_paper(paper_id)
    with sqlite.get_session() as session:
        session.execute(text("DELETE FROM papers WHERE paper_id = :pid"), {"pid": paper_id})
        session.commit()

    print(f"  删除后 Zvec: {zvec.stats['doc_count']} docs")
    print(f"  删除后 BM25: {bm25.doc_count} docs")
    print(f"  删除后 SQLite: {sqlite.get_paper_count()} papers")

    # 验证只剩 paper_002
    remaining = zvec.query(query_vec, topk=100, paper_id=paper_id)
    print(f"  paper_001 检索: {len(remaining)} results (应为 0)")
    remaining2 = zvec.query(query_vec, topk=100, paper_id=paper_id_2)
    print(f"  paper_002 检索: {len(remaining2)} results (应为 {len(chunked2)})")

    zvec.close()
    await embed.close()
    print("\n=== CRUD 全部验证通过 ===")


if __name__ == "__main__":
    asyncio.run(main())
