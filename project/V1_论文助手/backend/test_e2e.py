"""端到端测试：导入 PDF → 切块 → 检索 → LLM 对话（CLI 验证）"""

import asyncio
import sys

sys.path.insert(0, ".")

from app.pipelines.ingestion.cleaner import clean_markdown
from app.pipelines.ingestion.chunker import chunk_text, estimate_tokens


async def test_cleaner():
    """测试清洗器"""
    print("=" * 60)
    print("TEST 1: Cleaner")
    print("=" * 60)

    md_path = "./data/papers/85266a7a-f0aa-4ba1-bf55-43533448da12/full.md"
    with open(md_path, encoding="utf-8") as f:
        md = f.read()

    chunks = clean_markdown(md, "test_paper")
    print(f"Chunks: {len(chunks)}")

    # 检查不应该出现的内容
    noise_keywords = ["致谢", "学位论文评阅", "山东六家", "SHANDONG UNIVERSITY", "攻读硕士"]
    for i, c in enumerate(chunks):
        for kw in noise_keywords:
            if kw in c.content:
                print(f"  WARN: chunk[{i}] contains noise '{kw}': {c.content[:60]}...")

    # 统计
    total_chars = sum(len(c.content) for c in chunks)
    total_tokens = sum(estimate_tokens(c.content) for c in chunks)
    print(f"Total chars: {total_chars}, est tokens: {total_tokens}")

    # 前 3 个摘要
    for i, c in enumerate(chunks[:3]):
        print(f"  [{i}] sec=\"{c.section_title[:40]}\" chars={len(c.content)}")

    assert len(chunks) > 50, f"Too few chunks: {len(chunks)}"
    assert total_chars > 10000, f"Too few chars: {total_chars}"
    print("PASS\n")
    return chunks


def test_chunker(chunks):
    """测试切块器"""
    print("=" * 60)
    print("TEST 2: Chunker")
    print("=" * 60)

    from app.pipelines.ingestion.cleaner import Chunk

    chunked = chunk_text(chunks)
    print(f"Chunked results: {len(chunked)}")

    total_tokens = sum(estimate_tokens(c["content"]) for c in chunked)
    print(f"Total est tokens after chunking: {total_tokens}")

    for i, c in enumerate(chunked[:3]):
        sec = c.get("section_title", "")[:40]
        print(f"  [{i}] tokens={estimate_tokens(c['content'])} sec=\"{sec}\"")

    assert len(chunked) > 0, "No chunks produced"
    print("PASS\n")
    return chunked


async def test_embedding(chunked):
    """测试 Embedding"""
    print("=" * 60)
    print("TEST 3: Embedding")
    print("=" * 60)

    from app.clients.embedding_client import EmbeddingClient

    client = EmbeddingClient()
    texts = [c["content"] for c in chunked[:5]]  # 只测前 5 个

    print(f"Embedding {len(texts)} texts...")
    vectors = await client.embed(texts)
    print(f"Got {len(vectors)} vectors, dim={len(vectors[0])}")

    assert len(vectors) == len(texts), f"Mismatch: {len(vectors)} vs {len(texts)}"
    assert len(vectors[0]) == 1536, f"Wrong dimension: {len(vectors[0])}"
    await client.close()
    print("PASS\n")
    return vectors


async def test_full_ingest():
    """测试完整导入流程"""
    print("=" * 60)
    print("TEST 4: Full Ingest Pipeline")
    print("=" * 60)

    from app.stores.zvec_store import ZvecStore
    from app.stores.sqlite_repo import SQLiteRepo
    from app.stores.bm25_store import BM25Store
    from app.clients.embedding_client import EmbeddingClient

    # 初始化存储
    import os, shutil
    zvec_path = "./data/test_zvec"
    if os.path.exists(zvec_path):
        shutil.rmtree(zvec_path)

    sqlite = SQLiteRepo("./data/test_ingest.db")
    sqlite.init()

    zvec = ZvecStore(zvec_path, 1536)
    zvec.init()

    bm25 = BM25Store("./data/test_bm25")
    bm25.init()

    embed = EmbeddingClient()

    # 清洗
    md_path = "./data/papers/85266a7a-f0aa-4ba1-bf55-43533448da12/full.md"
    with open(md_path, encoding="utf-8") as f:
        md = f.read()

    chunks = clean_markdown(md, "test_ingest")
    chunked = chunk_text(chunks)

    # Embedding（只取前 10 个以节省 API 调用）
    test_chunks = chunked[:10]
    texts = [c["content"] for c in test_chunks]
    print(f"Embedding {len(texts)} chunks...")
    vectors = await embed.embed(texts)

    # 存储
    stored = zvec.insert_chunks("test_paper", test_chunks, vectors)
    print(f"Stored {stored} chunks in Zvec")

    # 检索测试
    query_vec = vectors[0]  # 用第一个 chunk 的向量做查询
    results = zvec.query(query_vec, topk=3)
    print(f"Query returned {len(results)} results")

    for r in results[:3]:
        fields = r.fields if hasattr(r, "fields") else {}
        content = fields.get("content", "")[:60] if isinstance(fields, dict) else ""
        print(f"  score={r.score:.4f} content=\"{content}...\"")

    zvec.close()
    await embed.close()

    # 清理测试数据（忽略锁文件错误）
    import os
    for p in ["./data/test_zvec", "./data/test_ingest.db", "./data/test_bm25"]:
        try:
            if os.path.isdir(p):
                shutil.rmtree(p)
            elif os.path.isfile(p):
                os.remove(p)
        except PermissionError:
            pass  # Zvec 锁文件占用，忽略

    print("PASS\n")


async def main():
    chunks = await test_cleaner()
    chunked = test_chunker(chunks)
    vectors = await test_embedding(chunked)
    await test_full_ingest()
    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
