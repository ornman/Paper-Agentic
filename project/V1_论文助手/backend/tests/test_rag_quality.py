"""RAG 质量对比测试：质量、速度、稳定性、溯源性

测试 5 个复杂问题，对比 RAG vs 纯 LLM

用法:
    uv run pytest tests/test_rag_quality.py -v -s
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
from app.stores.sqlite_repo import SQLiteRepo

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


class TestMetrics:
    """测试指标收集"""

    def __init__(self):
        self.results: list[dict] = []

    def add_result(
        self,
        mode: str,  # "RAG" or "Pure LLM"
        question_idx: int,
        question: str,
        metrics: dict,
    ):
        self.results.append({
            "mode": mode,
            "question_idx": question_idx,
            "question": question,
            **metrics,
        })

    def summarize(self) -> dict:
        """总结测试结果"""
        rag_results = [r for r in self.results if r["mode"] == "RAG"]
        llm_results = [r for r in self.results if r["mode"] == "Pure LLM"]

        return {
            "rag_avg_time": sum(r["total_time"] for r in rag_results) / len(rag_results) if rag_results else 0,
            "llm_avg_time": sum(r["total_time"] for r in llm_results) / len(llm_results) if llm_results else 0,
            "rag_avg_first_chunk": sum(r["first_chunk_time"] for r in rag_results) / len(rag_results) if rag_results else 0,
            "llm_avg_first_chunk": sum(r["first_chunk_time"] for r in llm_results) / len(llm_results) if llm_results else 0,
            "rag_total_tokens": sum(r.get("total_tokens", 0) for r in rag_results),
            "llm_total_tokens": sum(r.get("total_tokens", 0) for r in llm_results),
            "rag_source_count": sum(r.get("source_count", 0) for r in rag_results),
        }


async def test_rag_mode(qa_service: QAService, metrics: TestMetrics):
    """测试 RAG 模式"""
    logger.info("=" * 60)
    logger.info("开始 RAG 模式测试")
    logger.info("=" * 60)

    for i, question in enumerate(COMPLEX_QUESTIONS, 1):
        logger.info(f"\n--- 问题 {i}/5 (RAG) ---")
        logger.info(f"问题: {question[:80]}...")

        start = time.monotonic()
        first_chunk_time = None
        chunks: list[str] = []
        sources: list[dict] = []
        source_count = 0

        try:
            async for event in qa_service.query(
                session_id=f"rag_test_{i}",
                prompt=question,
            ):
                event_type = event.get("event", "")
                data = event.get("data", {})

                if event_type == "metadata":
                    source_count = len(data.get("sources", []))
                    sources = data.get("sources", [])
                    if first_chunk_time is None:
                        first_chunk_time = time.monotonic() - start

                elif event_type == "chunk":
                    chunk = data.get("content", "")
                    chunks.append(chunk)

                elif event_type == "done":
                    break

                elif event_type == "error":
                    logger.error(f"错误: {data.get('message', '')}")
                    break

            total_time = time.monotonic() - start
            total_tokens = estimate_tokens("".join(chunks))

            logger.info(f"首字耗时: {first_chunk_time:.2f}s")
            logger.info(f"总耗时: {total_time:.2f}s")
            logger.info(f"来源数: {source_count}")
            logger.info(f"Token数: {total_tokens}")
            logger.info(f"回答长度: {len(''.join(chunks))} 字")

            # 质量检查：是否有来源
            if source_count > 0:
                logger.info(f"✓ 有来源引用（{source_count} 个）")
            else:
                logger.warning("✗ 无来源引用")

            # 溯源检查：来源是否有具体信息
            if sources:
                sample = sources[0]
                if sample.get("title") and sample.get("page"):
                    logger.info(f"✓ 来源详情可验证: {sample['title'][:50]}... 第{sample['page']}页")
                else:
                    logger.warning("✗ 来源详情不完整")

            metrics.add_result("RAG", i, question, {
                "total_time": total_time,
                "first_chunk_time": first_chunk_time or 0,
                "total_tokens": total_tokens,
                "source_count": source_count,
                "has_sources": source_count > 0,
                "sources_have_details": bool(sources and sources[0].get("title")),
            })

        except Exception as e:
            logger.error(f"RAG 测试失败: {e}")
            metrics.add_result("RAG", i, question, {"error": str(e)})


async def test_pure_llm_mode(llm_client: LLMClient, metrics: TestMetrics):
    """测试纯 LLM 模式"""
    logger.info("=" * 60)
    logger.info("开始纯 LLM 模式测试")
    logger.info("=" * 60)

    for i, question in enumerate(COMPLEX_QUESTIONS, 1):
        logger.info(f"\n--- 问题 {i}/5 (Pure LLM) ---")
        logger.info(f"问题: {question[:80]}...")

        start = time.monotonic()
        first_chunk_time = None
        chunks: list[str] = []

        try:
            async for chunk in llm_client.chat_stream(messages=[{"role": "user", "content": question}]):
                if first_chunk_time is None:
                    first_chunk_time = time.monotonic() - start
                chunks.append(chunk)

            total_time = time.monotonic() - start
            total_tokens = estimate_tokens("".join(chunks))

            logger.info(f"首字耗时: {first_chunk_time:.2f}s")
            logger.info(f"总耗时: {total_time:.2f}s")
            logger.info(f"Token数: {total_tokens}")
            logger.info(f"回答长度: {len(''.join(chunks))} 字")
            logger.info("✗ 无来源引用（纯 LLM 模式）")

            metrics.add_result("Pure LLM", i, question, {
                "total_time": total_time,
                "first_chunk_time": first_chunk_time or 0,
                "total_tokens": total_tokens,
                "source_count": 0,
                "has_sources": False,
                "sources_have_details": False,
            })

            # 间隔 1 秒避免限流
            await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Pure LLM 测试失败: {e}")
            metrics.add_result("Pure LLM", i, question, {"error": str(e)})


@pytest.mark.asyncio
async def test_rag_quality_comparison():
    """RAG vs 纯 LLM 质量对比测试"""
    # 初始化依赖
    from app.stores.sqlite_repo import SQLiteRepo
    from app.stores.zvec_store import ZvecStore
    from app.stores.redis_cache import RedisCache
    from app.stores.bm25_store import BM25Store
    from app.api.v1.deps import init_deps

    sqlite = SQLiteRepo("./data/app.db")
    sqlite.init()
    zvec = ZvecStore("./data/zvec_db")
    zvec.init()

    # Redis 可选，如果不可用会降级运行
    redis = RedisCache()  # 测试环境可能没有 Redis，但代码有容错处理
    try:
        redis.init()
    except Exception:
        logger.warning("Redis 不可用，对话历史功能将被跳过")

    bm25 = BM25Store("./data/bm25_index")
    bm25.init()

    init_deps(sqlite, zvec, redis, bm25)

    qa_service = QAService()
    llm_client = LLMClient()

    metrics = TestMetrics()

    # 先测试 RAG 模式
    await test_rag_mode(qa_service, metrics)

    # 再测试纯 LLM 模式
    await test_pure_llm_mode(llm_client, metrics)

    # 关闭连接
    await qa_service.close()
    await llm_client.close()

    # 打印总结
    logger.info("\n" + "=" * 60)
    logger.info("测试总结")
    logger.info("=" * 60)

    summary = metrics.summarize()

    print(f"\nRAG 平均耗时: {summary['rag_avg_time']:.2f}s")
    print(f"Pure LLM 平均耗时: {summary['llm_avg_time']:.2f}s")

    print(f"\nRAG 平均首字: {summary['rag_avg_first_chunk']:.2f}s")
    print(f"Pure LLM 平均首字: {summary['llm_avg_first_chunk']:.2f}s")

    print(f"\nRAG 总 Token: {summary['rag_total_tokens']}")
    print(f"Pure LLM 总 Token: {summary['llm_total_tokens']}")

    print(f"\nRAG 平均来源数: {summary['rag_source_count'] / 5:.1f}")

    # 保存详细结果
    with open("tests/rag_quality_results.json", "w", encoding="utf-8") as f:
        json.dump(metrics.results, f, ensure_ascii=False, indent=2)

    logger.info("\n详细结果已保存到 tests/rag_quality_results.json")


if __name__ == "__main__":
    asyncio.run(test_rag_quality_comparison())
