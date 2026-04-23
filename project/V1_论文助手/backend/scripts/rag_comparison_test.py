"""RAG 性能对比测试：10 个问题测试 Chromadb vs 纯 LLM

结果保存到 CSV: data/rag_comparison_test.csv
"""

import asyncio
import csv
import json
import time
from datetime import datetime
from pathlib import Path

import httpx


API_BASE = "http://127.0.0.1:8000/api/v1"

# 10 个测试问题
QUESTIONS = [
    "什么是城乡一体化治理？",
    "公共数字文化资源整合有哪些主要模式？",
    "数字孪生技术在公共文化服务中有什么应用？",
    "如何评估公共文化服务的供给有效性？",
    "城乡社区治理面临哪些主要挑战？",
    "乡村振兴战略与城乡治理有什么关系？",
    "什么是文化治理，它有哪些特征？",
    "如何促进基本公共数字文化服务均等化？",
    "数字化如何促进公共文化服务精准化供给？",
    "空间治理视角下城乡规划如何转型？",
]


async def test_query(client: httpx.AsyncClient, session_id: str, question: str, enable_rag: bool) -> dict:
    """测试查询（RAG 或纯 LLM）"""
    start = time.time()
    response = await client.post(
        f"{API_BASE}/query",
        json={
            "session_id": session_id,
            "prompt": question,
            "enable_rag": enable_rag,
        },
        timeout=180,
    )
    elapsed = time.time() - start
    response.raise_for_status()

    # 解析 SSE 流
    sources = []
    answer_chunks = []
    buffer = ""

    async for line in response.aiter_lines():
        buffer += line + "\n"

        # SSE 格式: event: xxx\ndata: {...}\n\n
        if "\n\n" in buffer:
            parts = buffer.split("\n\n")
            buffer = parts[-1]  # 保留未完成的部分

            for part in parts[:-1]:
                lines = part.strip().split("\n")
                event = ""
                data_line = ""

                for line_str in lines:
                    if line_str.startswith("event:"):
                        event = line_str[6:].strip()
                    elif line_str.startswith("data:"):
                        data_line = line_str[5:].strip()

                if data_line:
                    try:
                        data = json.loads(data_line)
                        if event == "chunk":
                            content = data.get("content", "")
                            answer_chunks.append(content)
                        elif event == "metadata":
                            sources = data.get("sources", [])
                    except json.JSONDecodeError:
                        pass

    return {
        "mode": "RAG" if enable_rag else "Pure LLM",
        "question": question,
        "answer": "".join(answer_chunks),
        "source_count": len(sources),
        "elapsed_seconds": round(elapsed, 2),
        "sources": sources[:3],  # 只保留前 3 个
    }


async def main():
    output_dir = Path("./data")
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "rag_comparison_test.csv"

    results = []

    async with httpx.AsyncClient() as client:
        for i, question in enumerate(QUESTIONS, 1):
            print(f"\n[{i}/10] 问题: {question}")

            # 测试 RAG
            print("  测试 RAG 模式...")
            session_id_rag = f"test-rag-{datetime.now().strftime('%Y%m%d%H%M%S')}-{i}"
            try:
                rag_result = await test_query(client, session_id_rag, question, enable_rag=True)
                print(f"    RAG: {rag_result['elapsed_seconds']}s, {rag_result['source_count']} 个来源, {len(rag_result['answer'])} 字符")
                results.append(rag_result)
            except Exception as e:
                print(f"    RAG 失败: {e}")
                results.append({
                    "mode": "RAG",
                    "question": question,
                    "answer": f"[ERROR] {e}",
                    "source_count": 0,
                    "elapsed_seconds": 0,
                    "sources": [],
                })

            # 测试纯 LLM
            print("  测试纯 LLM 模式...")
            session_id_llm = f"test-llm-{datetime.now().strftime('%Y%m%d%H%M%S')}-{i}"
            try:
                llm_result = await test_query(client, session_id_llm, question, enable_rag=False)
                print(f"    LLM: {llm_result['elapsed_seconds']}s, {len(llm_result['answer'])} 字符")
                results.append(llm_result)
            except Exception as e:
                print(f"    LLM 失败: {e}")
                results.append({
                    "mode": "Pure LLM",
                    "question": question,
                    "answer": f"[ERROR] {e}",
                    "source_count": 0,
                    "elapsed_seconds": 0,
                    "sources": [],
                })

    # 保存到 CSV
    with open(output_file, "w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "mode", "question", "answer", "source_count", "elapsed_seconds",
            "source_1_title", "source_1_page", "source_2_title", "source_2_page", "source_3_title", "source_3_page",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for r in results:
            row = {
                "mode": r["mode"],
                "question": r["question"],
                # 截断答案到 500 字符以便查看
                "answer": (r["answer"][:500] + "...") if len(r["answer"]) > 500 else r["answer"],
                "source_count": r["source_count"],
                "elapsed_seconds": r["elapsed_seconds"],
            }
            for i in range(3):
                if i < len(r["sources"]):
                    s = r["sources"][i]
                    row[f"source_{i+1}_title"] = s.get("title", "")[:50]
                    row[f"source_{i+1}_page"] = s.get("page", "")
                else:
                    row[f"source_{i+1}_title"] = ""
                    row[f"source_{i+1}_page"] = ""
            writer.writerow(row)

    print(f"\n结果已保存到: {output_file}")

    # 统计摘要
    rag_results = [r for r in results if r["mode"] == "RAG"]
    llm_results = [r for r in results if r["mode"] == "Pure LLM"]

    rag_avg_time = sum(r["elapsed_seconds"] for r in rag_results) / len(rag_results) if rag_results else 0
    llm_avg_time = sum(r["elapsed_seconds"] for r in llm_results) / len(llm_results) if llm_results else 0
    rag_avg_sources = sum(r["source_count"] for r in rag_results) / len(rag_results) if rag_results else 0
    rag_avg_answer_len = sum(len(r["answer"]) for r in rag_results) / len(rag_results) if rag_results else 0
    llm_avg_answer_len = sum(len(r["answer"]) for r in llm_results) / len(llm_results) if llm_results else 0

    print("\n=== 统计摘要 ===")
    print(f"RAG 平均响应时间: {rag_avg_time:.2f}s")
    print(f"纯 LLM 平均响应时间: {llm_avg_time:.2f}s")
    print(f"RAG 平均来源数量: {rag_avg_sources:.1f}")
    print(f"RAG 平均答案长度: {rag_avg_answer_len:.0f} 字符")
    print(f"纯 LLM 平均答案长度: {llm_avg_answer_len:.0f} 字符")


if __name__ == "__main__":
    asyncio.run(main())
