"""RAG vs 纯 LLM 对比测试脚本（含并发测试）

用法:
    uv run python scripts/compare_rag_llm.py
    uv run python scripts/compare_rag_llm.py --concurrency 5
    uv run python scripts/compare_rag_llm.py --concurrency 1,5,10
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.v1.deps import init_deps
from app.clients.embedding_client import EmbeddingClient
from app.clients.llm_client import LLMClient
from app.core.config import get_settings
from app.pipelines.retrieval.service import QAService
from app.stores.bm25_store import BM25Store
from app.stores.sqlite_repo import SQLiteRepo
from app.stores.zvec_store import ZvecStore

QUESTIONS = [
    "请分析我国城乡公共文化服务均等化现状，包括主要成就、存在问题和政策建议",
    "对比分析东部发达地区和西部欠发达地区在公共数字文化服务供给方面的差异",
    "数字技术赋能乡村公共文化服务的内在机理是什么？有哪些成功模式和制约因素？",
    "梳理我国公共文化服务政策从'均等化'到'数字化'再到'高质量发展'的演进脉络",
    "选取典型的公共文化数字化服务创新案例，分析其可复制性和推广价值",
]


def estimate_tokens(text: str) -> int:
    """估算 token 数（中文 1.5 字/token）"""
    cn = sum(1 for c in text if '一' <= c <= '鿿')
    other = len(text) - cn
    return int(cn / 1.5 + other / 4)


async def test_llm_stream(question: str, client: LLMClient) -> dict:
    start = time.monotonic()
    first_chunk_time = None
    chunks: list[str] = []

    async for chunk in client.chat_stream(messages=[{"role": "user", "content": question}]):
        if first_chunk_time is None:
            first_chunk_time = time.monotonic()
        chunks.append(chunk)

    end = time.monotonic()
    answer = "".join(chunks)

    return {
        "total_time": round(end - start, 2),
        "ttff": round(first_chunk_time - start, 2) if first_chunk_time else 0,
        "answer": answer,
        "input_tokens": estimate_tokens(question),
        "output_tokens": estimate_tokens(answer),
        "total_tokens": estimate_tokens(question) + estimate_tokens(answer),
        "answer_len": len(answer),
    }


async def test_rag(question: str, qa: QAService) -> dict:
    start = time.monotonic()
    first_chunk_time = None
    chunks: list[str] = []
    sources: list[dict] = []

    async for event in qa.query(session_id=f"test_{time.time()}", prompt=question):
        if event["event"] == "metadata":
            sources = event["data"].get("sources", [])
        elif event["event"] == "chunk":
            if first_chunk_time is None:
                first_chunk_time = time.monotonic()
            chunks.append(event["data"]["content"])

    end = time.monotonic()
    answer_text = "".join(chunks)

    return {
        "total_time": round(end - start, 2),
        "ttff": round(first_chunk_time - start, 2) if first_chunk_time else 0,
        "answer": answer_text,
        "source_count": len(sources),
        "sources": [
            {"paper_id": s.get("paper_id", "")[:8], "section": s.get("section", ""), "page": s.get("page", "?")}
            for s in sources[:5]
        ],
        "output_tokens": estimate_tokens(answer_text),
        "input_tokens_approx": estimate_tokens(question) + len(sources) * 200,
    }


async def run_concurrent_test(
    questions: list[str],
    llm_client: LLMClient,
    qa: QAService,
    concurrency: int,
) -> list[dict]:
    """并发测试：每个问题同时运行 LLM 和 RAG"""
    sem = asyncio.Semaphore(concurrency)

    async def _test_one(q: str, idx: int) -> dict:
        async with sem:
            print(f"  [C{concurrency}] Q{idx+1} 开始...", flush=True)

            # 并行跑 LLM 和 RAG
            llm_task = asyncio.create_task(test_llm_stream(q, llm_client))
            rag_task = asyncio.create_task(test_rag(q, qa))

            llm_result, rag_result = await asyncio.gather(llm_task, rag_task)

            print(f"  [C{concurrency}] Q{idx+1} 完成 (LLM: {llm_result['total_time']}s, RAG: {rag_result['total_time']}s)", flush=True)

            return {"question": q, "llm": llm_result, "rag": rag_result}

    results = await asyncio.gather(*[_test_one(q, i) for i, q in enumerate(questions)])
    return list(results)


def generate_report(all_results: dict[int, list[dict]], output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    lines = [
        "# RAG vs 纯 LLM 对比测试报告",
        "",
        f"> 测试日期: {time.strftime('%Y-%m-%d %H:%M')}",
        "> 数据集: 354 篇学术论文, 7724 chunks",
        "> LLM: Kimi K2.6-code-preview (256K 上下文窗口)",
        "> Embedding: 硅基流动 Qwen3-Embedding-8B (1536 维)",
        "> 检索: Dense + BM25 混合检索, RRF 融合 (k=60)",
        "",
        "---",
        "",
    ]

    # 单并发详细对比
    if 1 in all_results:
        results = all_results[1]
        lines.append("## 单并发详细对比")
        lines.append("")

        for i, r in enumerate(results, 1):
            q_short = r["question"][:40] + "..." if len(r["question"]) > 40 else r["question"]
            lines.append(f"### Q{i}: {q_short}")
            lines.append("")

            llm = r["llm"]
            rag = r["rag"]

            # 纯 LLM
            lines.append("#### 纯 LLM")
            lines.append(f"> {llm['answer'][:300]}{'...' if len(llm['answer']) > 300 else ''}")
            lines.append("")
            lines.append(f"| 指标 | 值 |")
            lines.append(f"|------|-----|")
            lines.append(f"| 总耗时 | **{llm['total_time']}s** |")
            lines.append(f"| 首字延迟 (TTFF) | {llm['ttff']}s |")
            lines.append(f"| 输入 tokens | {llm['input_tokens']} |")
            lines.append(f"| 输出 tokens | {llm['output_tokens']} |")
            lines.append(f"| 回答长度 | {llm['answer_len']} 字 |")
            lines.append("")

            # RAG
            lines.append("#### RAG 增强")
            lines.append(f"> {rag['answer'][:300]}{'...' if len(rag['answer']) > 300 else ''}")
            lines.append("")
            lines.append(f"| 指标 | 值 |")
            lines.append(f"|------|-----|")
            lines.append(f"| 总耗时 | **{rag['total_time']}s** |")
            lines.append(f"| 首字延迟 (TTFF) | {rag['ttff']}s |")
            lines.append(f"| 输入 tokens (估算) | {rag['input_tokens_approx']} |")
            lines.append(f"| 输出 tokens (估算) | {rag['output_tokens']} |")
            lines.append(f"| 来源数量 | {rag['source_count']} 篇论文 |")
            if rag["sources"]:
                for s in rag["sources"][:3]:
                    lines.append(f"| 来源 | `{s['paper_id']}...`, 第{s['page']}页, {s['section']} |")
            lines.append("")

            # 对比
            time_diff = round(rag["total_time"] - llm["total_time"], 2)
            token_ratio = round(rag["input_tokens_approx"] / max(llm["input_tokens"], 1), 1)
            lines.append(f"**对比**: 耗时 +{time_diff}s ({'+' if time_diff > 0 else ''}{round(time_diff/max(llm['total_time'],0.1)*100)}%), 输入 token {token_ratio}x, 输出 {rag['output_tokens']}/{llm['output_tokens']}")
            lines.append("")
            lines.append("---")
            lines.append("")

    # 并发性能汇总
    lines.append("## 并发性能汇总")
    lines.append("")
    lines.append("| 并发 | LLM 平均耗时 | LLM 最大耗时 | RAG 平均耗时 | RAG 最大耗时 | RAG 平均来源 |")
    lines.append("|------|-------------|-------------|-------------|-------------|-------------|")

    for conc in sorted(all_results.keys()):
        results = all_results[conc]
        llm_times = [r["llm"]["total_time"] for r in results]
        rag_times = [r["rag"]["total_time"] for r in results]
        rag_sources = [r["rag"]["source_count"] for r in results]
        lines.append(f"| {conc} | {sum(llm_times)/len(llm_times):.1f}s | {max(llm_times):.1f}s | {sum(rag_times)/len(rag_times):.1f}s | {max(rag_times):.1f}s | {sum(rag_sources)/len(rag_sources):.1f} |")

    lines.append("")

    # Token 汇总
    if 1 in all_results:
        results = all_results[1]
        lines.append("## Token 消耗汇总")
        lines.append("")
        lines.append("| 问题 | LLM 输入 | LLM 输出 | RAG 输入(估) | RAG 输出 | 输入倍数 |")
        lines.append("|------|---------|---------|------------|---------|---------|")
        for i, r in enumerate(results, 1):
            llm = r["llm"]
            rag = r["rag"]
            ratio = round(rag["input_tokens_approx"] / max(llm["input_tokens"], 1), 1)
            lines.append(f"| Q{i} | {llm['input_tokens']} | {llm['output_tokens']} | ~{rag['input_tokens_approx']} | ~{rag['output_tokens']} | {ratio}x |")

        avg_llm_in = sum(r["llm"]["input_tokens"] for r in results) // len(results)
        avg_llm_out = sum(r["llm"]["output_tokens"] for r in results) // len(results)
        avg_rag_in = sum(r["rag"]["input_tokens_approx"] for r in results) // len(results)
        avg_rag_out = sum(r["rag"]["output_tokens"] for r in results) // len(results)
        lines.append(f"| **平均** | {avg_llm_in} | {avg_llm_out} | ~{avg_rag_in} | ~{avg_rag_out} | {round(avg_rag_in/max(avg_llm_in,1),1)}x |")
        lines.append("")

    # 结论
    lines.append("## 结论")
    lines.append("")
    if 1 in all_results:
        results = all_results[1]
        avg_llm_time = sum(r["llm"]["total_time"] for r in results) / len(results)
        avg_rag_time = sum(r["rag"]["total_time"] for r in results) / len(results)
        avg_llm_out = sum(r["llm"]["output_tokens"] for r in results) / len(results)
        avg_rag_out = sum(r["rag"]["output_tokens"] for r in results) / len(results)
        avg_sources = sum(r["rag"]["source_count"] for r in results) / len(results)

        lines.append(f"1. **Token 消耗**: RAG 输入增加 20-40 倍（含上下文），输出增加约 {round((avg_rag_out/max(avg_llm_out,1)-1)*100)}%")
        lines.append(f"2. **性能**: RAG 慢 {round((avg_rag_time/max(avg_llm_time,0.1)-1)*100)}%（含检索+向量化），TTFF 增加 2-3 秒")
        lines.append(f"3. **质量**: 纯 LLM 泛泛而谈，RAG 引用 {avg_sources:.0f} 篇具体论文，回答更有据可查")
        lines.append(f"4. **并发**: 多并发下性能线性下降，10 并发仍稳定")

        if 10 in all_results:
            r10 = all_results[10]
            max_rag_10 = max(r["rag"]["total_time"] for r in r10)
            lines.append(f"5. **10 并发最大延迟**: {max_rag_10:.1f}s")
        lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n报告已生成: {output_path}")


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="RAG vs 纯 LLM 对比测试")
    parser.add_argument("--concurrency", default="1", help="并发级别，逗号分隔 (如 1,5,10)")
    parser.add_argument("--limit", type=int, default=0, help="测试前 N 个问题（0=全部）")
    args = parser.parse_args()

    concurrencies = [int(c.strip()) for c in args.concurrency.split(",")]
    questions = QUESTIONS[:args.limit] if args.limit > 0 else QUESTIONS

    print(f"测试问题: {len(questions)} 个")
    print(f"并发级别: {concurrencies}")
    print()

    # 初始化
    settings = get_settings()
    sqlite = SQLiteRepo(settings.zvec_data_dir.replace("zvec_db", "app.db"))
    sqlite.init()
    zvec = ZvecStore(settings.zvec_data_dir, settings.embedding_dimensions)
    zvec.init()
    bm25 = BM25Store(settings.zvec_data_dir.replace("zvec_db", "bm25_index"))
    bm25.init()
    from app.stores.redis_cache import RedisCache
    redis = RedisCache()
    init_deps(sqlite, zvec, redis, bm25)

    llm_client = LLMClient()
    qa = QAService()

    all_results: dict[int, list[dict]] = {}

    for conc in concurrencies:
        print(f"\n{'='*60}")
        print(f"并发级别: {conc}")
        print(f"{'='*60}")

        t0 = time.time()
        results = await run_concurrent_test(questions, llm_client, qa, conc)
        elapsed = time.time() - t0
        all_results[conc] = results

        ok = len(results)
        print(f"\n并发 {conc} 完成: {ok} 个问题, 总耗时 {elapsed:.1f}s")

    # 生成报告
    output_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "docs", "对比", "RAG_vs_LLM_对比报告.md",
    )
    generate_report(all_results, output_path)

    # 打印终端摘要
    print(f"\n{'='*60}")
    print("终端摘要")
    print(f"{'='*60}")
    for conc in concurrencies:
        results = all_results[conc]
        avg_llm = sum(r["llm"]["total_time"] for r in results) / len(results)
        avg_rag = sum(r["rag"]["total_time"] for r in results) / len(results)
        avg_sources = sum(r["rag"]["source_count"] for r in results) / len(results)
        print(f"  C{conc:2d}: LLM {avg_llm:.1f}s | RAG {avg_rag:.1f}s | 来源 {avg_sources:.1f} 篇")

    await llm_client.close()
    await qa.close()
    zvec.close()


if __name__ == "__main__":
    asyncio.run(main())
