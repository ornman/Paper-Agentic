"""
端到端管道测试（清洗 → 切块 → Embedding → 存储 → 检索）

- test_cleaner_produces_chunks: 真实论文 MD 清洗后 >50 chunks, >10k chars
- test_cleaner_filters_noise:   清洗后不含"致谢/答辩表/校名"等噪音
- test_chunker_fixed_size:      切块后每块 ≤2000 tokens（上限容忍值）
- test_embedding_dimensions:    Embedding 返回 1536 维向量
- test_full_ingest_pipeline:    完整链路: 清洗→切块(取前10)→Embed→Zvec+BM25→检索验证

输入: 真实论文 MD (VR技术论文，78k chars)
"""

import os

import pytest

from app.pipelines.ingestion.cleaner import clean_markdown, Chunk
from app.pipelines.ingestion.chunker import chunk_text, estimate_tokens


def test_cleaner_produces_chunks(sample_md_path, sample_paper_id):
    with open(sample_md_path, encoding="utf-8") as f:
        md = f.read()
    chunks = clean_markdown(md, sample_paper_id)

    assert len(chunks) > 50
    assert sum(len(c.content) for c in chunks) > 10000


def test_cleaner_filters_noise(sample_md_path, sample_paper_id):
    with open(sample_md_path, encoding="utf-8") as f:
        md = f.read()
    chunks = clean_markdown(md, sample_paper_id)

    noise_keywords = ["致谢", "学位论文评阅", "SHANDONG UNIVERSITY", "攻读硕士"]
    for c in chunks:
        for kw in noise_keywords:
            assert kw not in c.content, f"Noise '{kw}' found in chunk"


def test_chunker_fixed_size(sample_md_path, sample_paper_id):
    with open(sample_md_path, encoding="utf-8") as f:
        md = f.read()
    chunks = clean_markdown(md, sample_paper_id)
    chunked = chunk_text(chunks)

    assert len(chunked) > 0
    for c in chunked:
        tokens = estimate_tokens(c["content"])
        assert tokens <= 2000, f"Chunk too large: {tokens} tokens"


@pytest.mark.asyncio
async def test_embedding_dimensions(embed_client):
    vectors = await embed_client.embed(["测试文本"])
    assert len(vectors) == 1
    assert len(vectors[0]) == 1536


@pytest.mark.asyncio
async def test_full_ingest_pipeline(temp_zvec, temp_bm25, temp_sqlite, embed_client, sample_md_path, sample_paper_id):
    with open(sample_md_path, encoding="utf-8") as f:
        md = f.read()

    # 清洗 → 切块
    chunks = clean_markdown(md, sample_paper_id)
    chunked = chunk_text(chunks)
    test_chunks = chunked[:10]
    texts = [c["content"] for c in test_chunks]

    # Embedding
    vectors = await embed_client.embed(texts)
    assert len(vectors) == len(test_chunks)

    # Zvec
    stored = temp_zvec.insert_chunks(
        sample_paper_id,
        [{**c, "file_hash": "e2e_hash", "paper_id": sample_paper_id} for c in test_chunks],
        vectors,
    )
    assert stored == len(test_chunks)

    # 检索
    results = temp_zvec.query(vectors[0], topk=3)
    assert len(results) >= 1

    # BM25
    doc_ids = [f"{sample_paper_id}_{i}" for i in range(len(test_chunks))]
    temp_bm25.add_documents(doc_ids, texts)
    bm25_results = temp_bm25.query("VR 数字化博物馆", topk=3)
    assert len(bm25_results) >= 1
