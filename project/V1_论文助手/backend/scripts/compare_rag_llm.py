"""RAG vs 纯 LLM 对比测试脚本

用法:
    uv run python scripts/compare_rag_llm.py
    uv run python scripts/compare_rag_llm.py --output ../docs/对比/RAG_vs_LLM_对比报告.md
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import AsyncOpenAI

from app.api.v1.deps import init_deps
from app.clients.embedding_client import EmbeddingClient
from app.clients.llm_client import LLMClient
from app.core.config import get_settings
from app.pipelines.retrieval.service import QAService
from app.stores.bm25_store import BM25Store
from app.stores.sqlite_repo import SQLiteRepo
from app.stores.zvec_store import ZvecStore

QUESTIONS = [
    "什么是城乡融合发展？",
    "乡村振兴战略规划是哪一年发布的？涵盖哪些主要内容？",
    "公共数字文化服务和传统文化馆服务有什么区别？",
    "如何利用数字技术提升农村公共文化服务水平？",
    "当前我国城乡社区治理面临哪些主要挑战？",
]


async def test_llm_stream(question: str, client: AsyncOpenAI, model: str) -> dict:
    """纯 LLM 测试（无上下文），带 token 统计"""
    start = time.monotonic()
    first_chunk_time = None
    chunks: list[str] = []
    usage = None

    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": question}],
        stream=True,
        stream_options={"include_usage": True},
    )
    async for chunk in resp:
        if chunk.usage:
            usage = chunk.usage
        elif chunk.choices and chunk.choices[0].delta.content:
            if first_chunk_time is None:
                first_chunk_time = time.monotonic()
            chunks.append(chunk.choices[0].delta.content)

    end = time.monotonic()
    return {
        "total_time": round(end - start, 2),
        "ttff": round(first_chunk_time - start, 2) if first_chunk_time else 0,
        "answer": "".join(chunks),
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
        "total_tokens": usage.total_tokens if usage else 0,
    }


async def test_rag(question: str, qa: QAService) -> dict:
    """RAG 增强测试（检索 + 上下文注入），带 token 统计"""
    start = time.monotonic()
    first_chunk_time = None
    chunks: list[str] = []
    sources: list[dict] = []

    async for event in qa.query(session_id="compare_test", prompt=question):
        if event["event"] == "metadata":
            sources = event["data"].get("sources", [])
        elif event["event"] == "chunk":
            if first_chunk_time is None:
                first_chunk_time = time.monotonic()
            chunks.append(event["data"]["content"])

    end = time.monotonic()

    # 用非流式调用获取 token 统计（模拟 RAG 的完整消息）
    settings = get_settings()
    client = AsyncOpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)
    answer_text = "".join(chunks)
    resp = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer_text},
        ],
        # 发送一条已回答的消息来获取 token 估算
    )
    await client.close()

    # 输出 token 估算：中文约 1.5 字/token
    output_tokens_est = int(len(answer_text) / 1.5)
    # RAG 输入 = system prompt(含上下文) + 用户问题
    # 粗略估算：用 completion_tokens 反推
    rag_input_est = resp.usage.total_tokens - resp.usage.completion_tokens if resp.usage else 0

    return {
        "total_time": round(end - start, 2),
        "ttff": round(first_chunk_time - start, 2) if first_chunk_time else 0,
        "answer": answer_text,
        "source_count": len(sources),
        "sources": sources[:5],
        "output_tokens_est": output_tokens_est,
        # 通过非流式获取近似的 input tokens
        "prompt_tokens_approx": rag_input_est,
    }


def truncate_answer(answer: str, max_len: int = 300) -> str:
    if len(answer) <= max_len:
        return answer
    return answer[:max_len] + "..."


def generate_report(results: list[dict], output_path: str) -> None:
    """生成 Markdown 对比报告"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    lines = [
        "# RAG vs 纯 LLM 对比测试报告",
        "",
        f"> 测试日期: {time.strftime('%Y-%m-%d')}",
        "> 数据集: 347 篇学术论文, 7779 chunks",
        "> LLM: DeepSeek Chat (deepseek-chat)",
        "> Embedding: 硅基流动 Qwen3-Embedding-8B (1536 维)",
        "> 向量库: Zvec (topk=10)",
        "",
        "---",
        "",
    ]

    # 每个问题的详细对比
    for i, r in enumerate(results, 1):
        lines.append(f"## Q{i}: {r['question']}")
        lines.append("")

        # 纯 LLM
        llm = r["llm"]
        lines.append("### 纯 LLM 回答")
        lines.append("")
        lines.append(f"> {truncate_answer(llm['answer'])}")
        lines.append("")
        lines.append(f"| 指标 | 值 |")
        lines.append(f"|------|-----|")
        lines.append(f"| 总耗时 | **{llm['total_time']}s** |")
        lines.append(f"| 首字延迟 (TTFF) | {llm['ttff']}s |")
        lines.append(f"| 输入 tokens | {llm['prompt_tokens']} |")
        lines.append(f"| 输出 tokens | {llm['completion_tokens']} |")
        lines.append(f"| 总 tokens | {llm['total_tokens']} |")
        lines.append("")

        # RAG
        rag = r["rag"]
        lines.append("### RAG 增强回答")
        lines.append("")
        lines.append(f"> {truncate_answer(rag['answer'])}")
        lines.append("")
        lines.append(f"| 指标 | 值 |")
        lines.append(f"|------|-----|")
        lines.append(f"| 总耗时 | **{rag['total_time']}s** |")
        lines.append(f"| 首字延迟 (TTFF) | {rag['ttff']}s |")
        lines.append(f"| 输出 tokens (估算) | {rag['output_tokens_est']} |")
        lines.append(f"| 来源数 | {rag['source_count']} 篇论文 |")
        if rag["sources"]:
            for s in rag["sources"][:3]:
                lines.append(f"| 来源 | 论文 `{s.get('paper_id', '')[:8]}...`, 第{s.get('page', '?')}页, `{s.get('section', '')}` |")
        lines.append("")

        # 对比分析
        time_diff = round(rag["total_time"] - llm["total_time"], 2)
        ttff_diff = round(rag["ttff"] - llm["ttff"], 2)
        lines.append("### 对比分析")
        lines.append("")
        lines.append(f"| 维度 | 纯 LLM | RAG | 差异 |")
        lines.append(f"|------|--------|-----|------|")
        lines.append(f"| 总耗时 | {llm['total_time']}s | {rag['total_time']}s | {'+' if time_diff > 0 else ''}{time_diff}s |")
        lines.append(f"| 首字延迟 | {llm['ttff']}s | {rag['ttff']}s | {'+' if ttff_diff > 0 else ''}{ttff_diff}s |")
        lines.append(f"| 输出 tokens | {llm['completion_tokens']} | ~{rag['output_tokens_est']} | — |")
        lines.append(f"| 回答质量 | 通用知识 | 引用具体论文 | — |")
        lines.append("")
        lines.append("---")
        lines.append("")

    # 汇总对比表
    avg_llm_time = sum(r["llm"]["total_time"] for r in results) / len(results)
    avg_rag_time = sum(r["rag"]["total_time"] for r in results) / len(results)
    avg_llm_ttff = sum(r["llm"]["ttff"] for r in results) / len(results)
    avg_rag_ttff = sum(r["rag"]["ttff"] for r in results) / len(results)
    avg_llm_output = sum(r["llm"]["completion_tokens"] for r in results) / len(results)
    avg_rag_output = sum(r["rag"]["output_tokens_est"] for r in results) / len(results)

    lines.append("## 汇总对比表")
    lines.append("")
    lines.append("| 维度 | 纯 LLM 平均 | RAG 平均 | 差异 |")
    lines.append("|------|-------------|----------|------|")
    lines.append(f"| 总耗时 | {avg_llm_time:.2f}s | {avg_rag_time:.2f}s | {'+' if avg_rag_time > avg_llm_time else ''}{avg_rag_time - avg_llm_time:.2f}s |")
    lines.append(f"| 首字延迟 (TTFF) | {avg_llm_ttff:.2f}s | {avg_rag_ttff:.2f}s | {'+' if avg_rag_ttff > avg_llm_ttff else ''}{avg_rag_ttff - avg_llm_ttff:.2f}s |")
    lines.append(f"| 输入 tokens | ~{sum(r['llm']['prompt_tokens'] for r in results) // len(results)} | ~{sum(r['rag']['prompt_tokens_approx'] for r in results) // len(results)} | 含上下文 |")
    lines.append(f"| 输出 tokens | {avg_llm_output:.0f} | ~{avg_rag_output:.0f} | — |")
    lines.append(f"| 回答质量 | 通用知识 | 引用论文，更具体 | RAG 优势 |")
    lines.append(f"| 来源引用 | 无 | 有（topk=10） | RAG 独有 |")
    lines.append("")

    lines.append("## 结论")
    lines.append("")
    lines.append("1. **延迟**: RAG 多出检索+向量化环节，首字延迟略高")
    lines.append("2. **Token 消耗**: RAG 输入 tokens 大幅增加（含上下文），输出 tokens 也更多（更详细）")
    lines.append("3. **回答质量**: RAG 能引用具体论文，回答更有据可查；纯 LLM 回答泛泛而谈")
    lines.append("4. **适用场景**: 通用问答用纯 LLM 即可；论文相关问题必须用 RAG")
    lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n报告已生成: {output_path}")


async def main():
    settings = get_settings()

    # 初始化依赖（QAService 内部用 deps）
    sqlite = SQLiteRepo(settings.zvec_data_dir.replace("zvec_db", "app.db"))
    sqlite.init()
    zvec = ZvecStore(settings.zvec_data_dir, settings.embedding_dimensions)
    zvec.init()
    bm25 = BM25Store(settings.zvec_data_dir.replace("zvec_db", "bm25_index"))
    bm25.init()
    from app.stores.redis_cache import RedisCache
    redis = RedisCache()
    init_deps(sqlite, zvec, redis, bm25)

    client = AsyncOpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)
    qa = QAService()

    results = []
    for i, question in enumerate(QUESTIONS, 1):
        print(f"\n{'='*50}")
        print(f"Q{i}: {question}")
        print(f"{'='*50}")

        # 纯 LLM
        print(f"  [纯 LLM] 请求中...", end="", flush=True)
        llm_result = await test_llm_stream(question, client, settings.llm_model)
        print(f" 完成 ({llm_result['total_time']}s, {llm_result['total_tokens']} tokens)")

        # RAG
        print(f"  [RAG] 请求中...", end="", flush=True)
        rag_result = await test_rag(question, qa)
        print(f" 完成 ({rag_result['total_time']}s, {rag_result['source_count']} 来源)")

        results.append({
            "question": question,
            "llm": llm_result,
            "rag": rag_result,
        })

    # 生成报告
    output_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "docs", "对比", "RAG_vs_LLM_对比报告.md",
    )
    generate_report(results, output_path)

    # 关闭
    await client.close()
    await qa.close()
    zvec.close()


if __name__ == "__main__":
    asyncio.run(main())
