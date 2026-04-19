"""
三存储层 CRUD 验证（使用临时实例，互不干扰）

Zvec (3 个用例):
- test_zvec_insert_and_query:  插入 10 chunks → 查询 top5，验证 top1 score > 0.9
- test_zvec_filter_by_paper:   插入两篇论文 → 按 paper_id 过滤，只返回指定的那篇
- test_zvec_delete_paper:      插入 → 删除 → 确认 doc_count 归零

BM25 (2 个用例):
- test_bm25_add_and_query:     索引 10 docs → 关键词检索 "VR 虚拟现实"，有结果
- test_bm25_delete:            索引 → 删除 → 确认 doc_count 归零

SQLite (3 个用例):
- test_sqlite_insert_and_query: INSERT → SELECT，验证 title 读写
- test_sqlite_update:           INSERT → UPDATE title → 验证修改生效
- test_sqlite_delete:           INSERT → DELETE → 确认 count 归零

数据来源: sample_md_path 论文经 cleaner + chunker 处理后的真实 chunks
"""

import os

import pytest
from sqlalchemy import text

from app.clients.embedding_client import EmbeddingClient
from app.pipelines.ingestion.chunker import chunk_text, estimate_tokens
from app.pipelines.ingestion.cleaner import clean_markdown


@pytest.fixture
def paper_chunks(sample_md_path, sample_paper_id):
    with open(sample_md_path, encoding="utf-8") as f:
        md = f.read()
    chunks = clean_markdown(md, sample_paper_id)
    return chunk_text(chunks)


@pytest.mark.asyncio
async def test_zvec_insert_and_query(temp_zvec, embed_client, paper_chunks, sample_paper_id):
    texts = [c["content"] for c in paper_chunks[:10]]
    vectors = await embed_client.embed(texts)

    stored = temp_zvec.insert_chunks(
        sample_paper_id,
        [{**c, "file_hash": "test_hash", "paper_id": sample_paper_id} for c in paper_chunks[:10]],
        vectors,
    )
    assert stored == 10
    assert temp_zvec.stats["doc_count"] == 10

    results = temp_zvec.query(vectors[0], topk=5)
    assert len(results) >= 1
    assert results[0].score > 0.9


@pytest.mark.asyncio
async def test_zvec_filter_by_paper(temp_zvec, embed_client, paper_chunks, sample_paper_id):
    texts = [c["content"] for c in paper_chunks[:5]]
    vectors = await embed_client.embed(texts)

    temp_zvec.insert_chunks(
        sample_paper_id,
        [{**c, "file_hash": "h1", "paper_id": sample_paper_id} for c in paper_chunks[:5]],
        vectors,
    )
    temp_zvec.insert_chunks(
        "other_paper",
        [{**c, "file_hash": "h2", "paper_id": "other_paper"} for c in paper_chunks[:5]],
        vectors,
    )

    filtered = temp_zvec.query(vectors[0], topk=100, paper_id=sample_paper_id)
    for r in filtered:
        fields = r.fields if hasattr(r, "fields") else {}
        if isinstance(fields, dict):
            assert fields.get("paper_id") == sample_paper_id


def test_zvec_delete_paper(temp_zvec, embed_client, paper_chunks, sample_paper_id):
    import asyncio

    texts = [c["content"] for c in paper_chunks[:5]]
    vectors = asyncio.get_event_loop().run_until_complete(embed_client.embed(texts))

    temp_zvec.insert_chunks(
        sample_paper_id,
        [{**c, "file_hash": "h1", "paper_id": sample_paper_id} for c in paper_chunks[:5]],
        vectors,
    )
    assert temp_zvec.stats["doc_count"] == 5

    temp_zvec.delete_paper(sample_paper_id)
    assert temp_zvec.stats["doc_count"] == 0


def test_bm25_add_and_query(temp_bm25, paper_chunks, sample_paper_id):
    texts = [c["content"] for c in paper_chunks[:10]]
    doc_ids = [f"{sample_paper_id}_{i}" for i in range(10)]

    temp_bm25.add_documents(doc_ids, texts)
    assert temp_bm25.doc_count == 10

    results = temp_bm25.query("VR 虚拟现实", topk=5)
    assert len(results) >= 1


def test_bm25_delete(temp_bm25, paper_chunks, sample_paper_id):
    texts = [c["content"] for c in paper_chunks[:5]]
    doc_ids = [f"{sample_paper_id}_{i}" for i in range(5)]

    temp_bm25.add_documents(doc_ids, texts)
    assert temp_bm25.doc_count == 5

    temp_bm25.delete_paper(sample_paper_id)
    assert temp_bm25.doc_count == 0


def test_sqlite_insert_and_query(temp_sqlite, sample_paper_id, sample_md_path):
    with temp_sqlite.get_session() as session:
        session.execute(text("""
            INSERT INTO papers (paper_id, title, authors, file_path, file_hash,
                file_size, chunk_count, import_time, status)
            VALUES (:pid, :title, '', :path, :hash, :size, :chunks, :time, 'completed')
        """), {
            "pid": sample_paper_id,
            "title": "测试论文",
            "path": sample_md_path,
            "hash": "test_hash",
            "size": 1000,
            "chunks": 10,
            "time": "2026-04-19T00:00:00",
        })
        session.commit()

    assert temp_sqlite.get_paper_count() == 1

    with temp_sqlite.get_session() as session:
        row = session.execute(text(
            "SELECT title FROM papers WHERE paper_id = :pid"
        ), {"pid": sample_paper_id}).fetchone()
    assert row[0] == "测试论文"


def test_sqlite_update(temp_sqlite, sample_paper_id, sample_md_path):
    with temp_sqlite.get_session() as session:
        session.execute(text("""
            INSERT INTO papers (paper_id, title, authors, file_path, file_hash,
                file_size, chunk_count, import_time, status)
            VALUES (:pid, :title, '', :path, :hash, 0, 0, :time, 'completed')
        """), {
            "pid": sample_paper_id, "title": "原标题",
            "path": sample_md_path, "hash": "h",
            "time": "2026-04-19T00:00:00",
        })
        session.commit()

    with temp_sqlite.get_session() as session:
        session.execute(text(
            "UPDATE papers SET title = :t WHERE paper_id = :pid"
        ), {"t": "新标题", "pid": sample_paper_id})
        session.commit()

    with temp_sqlite.get_session() as session:
        row = session.execute(text(
            "SELECT title FROM papers WHERE paper_id = :pid"
        ), {"pid": sample_paper_id}).fetchone()
    assert row[0] == "新标题"


def test_sqlite_delete(temp_sqlite, sample_paper_id, sample_md_path):
    with temp_sqlite.get_session() as session:
        session.execute(text("""
            INSERT INTO papers (paper_id, title, authors, file_path, file_hash,
                file_size, chunk_count, import_time, status)
            VALUES (:pid, '', '', :path, '', 0, 0, :time, 'completed')
        """), {
            "pid": sample_paper_id, "path": sample_md_path,
            "time": "2026-04-19T00:00:00",
        })
        session.commit()

    assert temp_sqlite.get_paper_count() == 1

    with temp_sqlite.get_session() as session:
        session.execute(text("DELETE FROM papers WHERE paper_id = :pid"), {"pid": sample_paper_id})
        session.commit()

    assert temp_sqlite.get_paper_count() == 0
