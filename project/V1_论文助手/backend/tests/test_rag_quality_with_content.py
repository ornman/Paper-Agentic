"""RAG 质量对比测试：保存实际回答内容

测试 5 个复杂问题，对比 RAG vs 纯 LLM 的内容质量

用法:
    uv run pytest tests/test_rag_quality_with_content.py -v -s
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import pytest

from app.api.v1.deps import init_deps
from app.clients.llm_client import LLMClient
from app.pipelines.retrieval.service import QAService
from app.stores.bm25_store import BM25Store
from app.stores.redis_cache import RedisCache
from app.stores.sqlite_repo import SQLiteRepo
from app.stores.zvec_store import ZvecStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag_quality_test")


# 5 个复杂问题
COMPLEX_QUESTIONS = [
    "1. 请综合分析我国城乡社区治理的主要模式和特征，包括治理主体的构成、治理机制的运作方式、以及存在的突出问题。请结合具体案例和数据进行分析。",

    "2. 梳理我国城乡关系政策从'城乡二元'到'城乡统筹'再到'城乡融合'的演进脉络，分析每个阶段的核心政策工具、改革重点和实施效果。请引用具体政策文件和实施时间。",

    "3. 专业合作组织在农村环境治理中有哪些功能和优势？又面临哪些制约因素？请结合具体实践案例进行分析，并提出相应的引导措施。",

    "4. 对比分析东部发达地区和西部欠发达地区在公共数字文化服务供给方面的差异，包括基础设施、服务内容、供给模式等方面的不同，并分析造成这些差异的深层原因。",

    "5. 数字技术如何赋能乡村公共文化服务？其内在机理是什么？有哪些成功模式和制约因素？请结合具体案例进行分析，并评估其可复制性和推广价值。",
]


def estimate_tokens(text: str) -> int:
    """估算 token 数（中文 1.5 字/token）"""
    cn = sum(1 for c in text if '一' <= c <= '鿿')
    other = len(text) - cn
    return int(cn / 1.5 + other / 4)


@pytest.mark.asyncio
async def test_rag_quality_with_content():
    """RAG vs 纯 LLM 质量对比测试（保存内容）"""
    # 初始化依赖
    sqlite = SQLiteRepo("./data/app.db")
    sqlite.init()
    zvec = ZvecStore("./data/zvec_db")
    zvec.init()

    redis = RedisCache()
    try:
        await redis.init()
    except Exception:
        logger.warning("Redis 不可用，对话历史功能将被跳过")

    bm25 = BM25Store("./data/bm25_index")
    bm25.init()

    init_deps(sqlite, zvec, redis, bm25)

    qa_service = QAService()
    llm_client = LLMClient()

    results = []

    logger.info("=" * 60)
    logger.info("开始 RAG vs Pure LLM 内容质量对比")
    logger.info("=" * 60)

    for i, question in enumerate(COMPLEX_QUESTIONS, 1):
        logger.info(f"\n{'=' * 60}")
        logger.info(f"问题 {i}/5")
        logger.info(f"{'=' * 60}")
        logger.info(f"问题: {question[:80]}...")

        # ========== RAG 模式 ==========
        logger.info("\n--- RAG 模式 ---")
        rag_start = time.monotonic()
        rag_chunks = []
        rag_sources = []

        async for event in qa_service.query(
            session_id=f"rag_test_{i}",
            prompt=question,
        ):
            event_type = event.get("event", "")
            data = event.get("data", {})

            if event_type == "metadata":
                rag_sources = data.get("sources", [])

            elif event_type == "chunk":
                rag_chunks.append(data.get("content", ""))

            elif event_type == "done":
                break

        rag_time = time.monotonic() - rag_start
        rag_answer = "".join(rag_chunks)
        rag_tokens = estimate_tokens(rag_answer)

        logger.info(f"耗时: {rag_time:.2f}s")
        logger.info(f"Token: {rag_tokens}")
        logger.info(f"来源数: {len(rag_sources)}")
        logger.info(f"回答长度: {len(rag_answer)} 字")
        logger.info(f"回答预览: {rag_answer[:200]}...")

        # 间隔 1 秒
        await asyncio.sleep(1)

        # ========== Pure LLM 模式 ==========
        logger.info("\n--- Pure LLM 模式 ---")
        llm_start = time.monotonic()
        llm_chunks = []

        async for chunk in llm_client.chat_stream(messages=[{"role": "user", "content": question}]):
            llm_chunks.append(chunk)

        llm_time = time.monotonic() - llm_start
        llm_answer = "".join(llm_chunks)
        llm_tokens = estimate_tokens(llm_answer)

        logger.info(f"耗时: {llm_time:.2f}s")
        logger.info(f"Token: {llm_tokens}")
        logger.info(f"回答长度: {len(llm_answer)} 字")
        logger.info(f"回答预览: {llm_answer[:200]}...")

        # 记录结果
        results.append({
            "question_idx": i,
            "question": question,
            "rag": {
                "time": rag_time,
                "tokens": rag_tokens,
                "answer": rag_answer,
                "sources": rag_sources,
                "length": len(rag_answer),
            },
            "llm": {
                "time": llm_time,
                "tokens": llm_tokens,
                "answer": llm_answer,
                "length": len(llm_answer),
            },
            "comparison": {
                "time_diff": rag_time - llm_time,
                "time_diff_pct": ((rag_time - llm_time) / llm_time * 100) if llm_time > 0 else 0,
                "token_diff": rag_tokens - llm_tokens,
                "token_diff_pct": ((rag_tokens - llm_tokens) / llm_tokens * 100) if llm_tokens > 0 else 0,
            }
        })

        # 间隔 1 秒
        await asyncio.sleep(1)

    # 关闭连接
    await qa_service.close()
    await llm_client.close()

    # 保存完整结果
    output_file = "tests/rag_quality_with_content.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info(f"\n{'=' * 60}")
    logger.info("测试总结")
    logger.info(f"{'=' * 60}")

    # 统计
    rag_avg_time = sum(r["rag"]["time"] for r in results) / len(results)
    llm_avg_time = sum(r["llm"]["time"] for r in results) / len(results)
    rag_avg_tokens = sum(r["rag"]["tokens"] for r in results) / len(results)
    llm_avg_tokens = sum(r["llm"]["tokens"] for r in results) / len(results)

    print(f"\nRAG 平均耗时: {rag_avg_time:.2f}s")
    print(f"Pure LLM 平均耗时: {llm_avg_time:.2f}s")
    print(f"速度差异: {rag_avg_time - llm_avg_time:+.2f}s ({(rag_avg_time - llm_avg_time) / llm_avg_time * 100:+.1f}%)")

    print(f"\nRAG 平均 Token: {rag_avg_tokens:.0f}")
    print(f"Pure LLM 平均 Token: {llm_avg_tokens:.0f}")
    print(f"Token 差异: {rag_avg_tokens - llm_avg_tokens:+.0f} ({(rag_avg_tokens - llm_avg_tokens) / llm_avg_tokens * 100:+.1f}%)")

    logger.info(f"\n完整结果已保存到 {output_file}")
    logger.info("请查看文件对比 RAG 和 Pure LLM 的回答内容质量")


if __name__ == "__main__":
    asyncio.run(test_rag_quality_with_content())
