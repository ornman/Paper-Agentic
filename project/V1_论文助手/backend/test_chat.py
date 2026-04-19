"""CLI 对话测试：检索 + LLM 流式"""

import asyncio
import sys

sys.path.insert(0, ".")


async def test_chat():
    from app.clients.embedding_client import EmbeddingClient
    from app.clients.llm_client import LLMClient

    embed = EmbeddingClient()
    llm = LLMClient()

    # 用一个简单的查询测试
    query = "VR技术在数字化博物馆中的应用有哪些？"
    print(f"Query: {query}")
    print()

    # Embedding
    print("Embedding query...")
    vec = await embed.embed_single(query)
    print(f"Vector dim: {len(vec)}")

    # LLM 直接对话（不经过检索，测试 LLM 连通性）
    print()
    print("--- LLM Response (no retrieval) ---")
    full = []
    async for chunk in llm.chat_stream([
        {"role": "system", "content": "你是一个学术论文助手，用中文简洁回答。"},
        {"role": "user", "content": query},
    ]):
        full.append(chunk)
        print(chunk, end="", flush=True)
    print()
    print(f"\nResponse length: {sum(len(c) for c in full)} chars")

    await llm.close()
    await embed.close()
    print("\nCHAT TEST PASSED")


if __name__ == "__main__":
    asyncio.run(test_chat())
