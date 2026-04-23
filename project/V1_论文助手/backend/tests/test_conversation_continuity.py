"""对话连续性测试：同一会话 10 轮对话验证上下文记忆

测试内容：
1. 第 1-5 轮：建立上下文（自我介绍、讨论学术话题）
2. 第 6-10 轮：测试记忆回溯（名字、研究方向、讨论内容）

关键：所有查询使用同一个 session_id，共享对话历史

用法:
    uv run pytest tests/test_conversation_continuity.py -v -s
"""

from __future__ import annotations

import asyncio
import json
import logging

import pytest

from app.api.v1.deps import init_deps
from app.pipelines.retrieval.service import QAService
from app.stores.bm25_store import BM25Store
from app.stores.memory_cache import MemoryCache
from app.stores.redis_cache import RedisCache
from app.stores.sqlite_repo import SQLiteRepo
from app.stores.zvec_store import ZvecStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("continuity_test")

# 统一 session_id —— 所有查询共享同一会话
SESSION_ID = "continuity_test"

# 10 轮对话流程
QUESTIONS = [
    # 第 1-5 轮：建立上下文
    "你好，我叫小明，是一名研究生，正在研究城乡社区治理。请简单介绍一下这个领域的研究背景。",
    "我想了解城乡社区治理的主要模式和特征有哪些？",
    "城乡关系政策是如何演进的？从二元到融合经历了哪些阶段？",
    "专业合作组织在农村环境治理中有什么作用？",
    "东西部地区在公共数字文化服务方面有什么差异？",

    # 第 6-10 轮：测试记忆回溯
    "我叫什么名字？我的研究方向是什么？",
    "我之前问了几个问题？请列举一下。",
    "我们在第二个问题中讨论了什么内容？",
    "请总结一下我们刚才讨论的主要内容。",
    "我对哪个问题最感兴趣？根据我们的对话记录判断。",
]

# 记忆回溯的期望关键词（第 6-10 轮）
EXPECTED_KEYWORDS = {
    6: ["小明", "研究生", "城乡社区治理"],       # 名字 + 研究方向
    7: ["5", "五", "模式", "演进", "治理"],      # 列举问题
    8: ["模式", "特征", "行政", "自治", "共治"],  # 第二个问题的内容
    9: ["社区治理", "政策", "环境", "数字文化"],  # 总结内容
    10: ["社区治理", "治理"],                      # 兴趣判断
}


@pytest.mark.asyncio
async def test_conversation_continuity():
    """测试对话连续性（10 轮同一会话）"""
    # 初始化依赖
    sqlite = SQLiteRepo("./data/app.db")
    sqlite.init()
    zvec = ZvecStore("./data/zvec_db")
    zvec.init()

    # 尝试使用 Redis，失败则使用内存存储
    redis = RedisCache()
    try:
        await redis.init()
        logger.info("Redis 连接成功")
    except Exception as e:
        logger.warning(f"Redis 不可用 ({e})，使用内存存储替代")
        redis = MemoryCache()
        await redis.init()

    bm25 = BM25Store("./data/bm25_index")
    bm25.init()

    init_deps(sqlite, zvec, redis, bm25)

    # 清除旧的对话历史
    try:
        await redis.delete_conversation(SESSION_ID)
        logger.info("已清除旧的对话历史")
    except Exception:
        pass

    qa_service = QAService()

    # 记录对话
    history: list[dict] = []
    results: list[dict] = []

    logger.info("=" * 60)
    logger.info(f"开始对话连续性测试 (session_id={SESSION_ID})")
    logger.info("=" * 60)

    for i, question in enumerate(QUESTIONS, 1):
        logger.info(f"\n--- 第 {i}/10 轮对话 ---")
        logger.info(f"问题: {question[:60]}...")

        response_chunks = []
        sources = []

        try:
            async for event in qa_service.query(
                session_id=SESSION_ID,
                prompt=question,
            ):
                event_type = event.get("event", "")
                data = event.get("data", {})

                if event_type == "metadata":
                    sources = data.get("sources", [])

                elif event_type == "chunk":
                    response_chunks.append(data.get("content", ""))

                elif event_type == "done":
                    break

            response = "".join(response_chunks)

            # 记录对话
            history.append({
                "round": i,
                "question": question,
                "answer": response,
                "answer_length": len(response),
                "source_count": len(sources),
            })

            logger.info(f"回答长度: {len(response)} 字")
            logger.info(f"来源数: {len(sources)}")

            # 第 6-10 轮：测试记忆回溯
            if i >= 6:
                has_context, matched = _check_context(i, response)
                results.append({
                    "round": i,
                    "question": question,
                    "answer_preview": response[:300],
                    "has_context": has_context,
                    "matched_keywords": matched,
                    "expected_keywords": EXPECTED_KEYWORDS.get(i, []),
                    "answer_length": len(response),
                })

                status = "PASS" if has_context else "FAIL"
                logger.info(f"记忆回溯: {status} (匹配: {matched})")
                logger.info(f"回答预览: {response[:200]}...")

            # 每轮间隔 1 秒避免限流
            await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"第 {i} 轮失败: {e}")
            results.append({
                "round": i,
                "error": str(e),
            })

    # 关闭连接
    await qa_service.close()

    # 打印总结
    logger.info("\n" + "=" * 60)
    logger.info("对话连续性测试总结")
    logger.info("=" * 60)

    passed = sum(1 for r in results if r.get("has_context"))
    total = len(results)

    print(f"\n记忆回溯测试: {passed}/{total} 通过")

    for r in results:
        status = "PASS" if r.get("has_context") else "FAIL"
        print(f"  轮次 {r['round']}: {status} — {r['question'][:30]}...")

    # 保存结果
    with open("tests/conversation_continuity_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "session_id": SESSION_ID,
            "history": history,
            "results": results,
            "summary": {
                "total_rounds": len(QUESTIONS),
                "context_aware": passed,
                "total_tested": total,
            }
        }, f, ensure_ascii=False, indent=2)

    logger.info("\n详细结果已保存到 tests/conversation_continuity_results.json")


def _check_context(round_idx: int, response: str) -> tuple[bool, list[str]]:
    """检查回答是否包含期望的上下文关键词

    Returns:
        (has_context, matched_keywords)
    """
    expected = EXPECTED_KEYWORDS.get(round_idx, [])
    matched = [kw for kw in expected if kw in response]
    # 至少匹配一半的期望关键词
    has_context = len(matched) >= max(1, len(expected) // 2)
    return has_context, matched


if __name__ == "__main__":
    asyncio.run(test_conversation_continuity())
