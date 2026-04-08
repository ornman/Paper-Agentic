#!/usr/bin/env python
"""
阶段 4 测试：检索验证
用简单的查询测试 ChromaDB 向量检索和 BM25 关键词检索是否能返回结果。
"""
import asyncio
from app.clients.embedding_client import EmbeddingClient
from app.repositories.chroma_repo import ChromaRepo
from app.repositories.bm25_repo import BM25Repo


async def main():
    query = "城乡公共文化服务的差距"
    print(f"查询: {query}\n")

    # --- 向量检索 ---
    print("--- 向量检索 (ChromaDB) ---")
    embedding_client = EmbeddingClient()
    query_embedding = await embedding_client.embed_single(query)
    print(f"Query 向量维度: {len(query_embedding)}")

    chroma = ChromaRepo()
    results = chroma.query(query_embedding, top_k=5)

    for i, (doc, meta, dist) in enumerate(zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    )):
        preview = doc[:80] + ("..." if len(doc) > 80 else "")
        print(f"\n  [{i+1}] distance={dist:.4f}  来源={meta.get('document','?')}  page={meta.get('page','?')}")
        print(f"      {preview}")

    # --- BM25 检索 ---
    print(f"\n--- BM25 检索 ---")
    bm25 = BM25Repo()
    bm25_results = bm25.query(query, top_k=5)

    if not bm25_results:
        print("  无结果")
    else:
        for i, (doc_id, score) in enumerate(bm25_results):
            print(f"  [{i+1}] id={doc_id}  score={score:.4f}")

    print(f"\n检索测试完成。")


if __name__ == "__main__":
    asyncio.run(main())
