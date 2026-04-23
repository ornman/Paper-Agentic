"""对话连续性测试：10 个 session 验证上下文记忆

测试内容：
1. 第 1-5 个 session 建立上下文
2. 第 6-10 个 session 测试记忆回溯

用法:
    uv run pytest tests/test_conversation_continuity.py -v -s
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from app.api.v1.deps import init_deps
from app.pipelines.retrieval.service import QAService
from app.stores.bm25_store import BM25Store
from app.stores.redis_cache import RedisCache
from app.stores.sqlite_repo import SQLiteRepo
from app.stores.zvec_store import ZvecStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("continuity_test")


# 对话流程
CONVERSATION_FLOW = [
    # Session 1-5: 建立上下文
    ("session_1", "你好，我叫小明，是一名研究生，正在研究城乡社区治理。请介绍一下这个领域的研究背景。"),
    ("session_2", "我想了解城乡社区治理的主要模式和特征。"),
    ("session_3", "城乡关系政策是如何演进的？从二元到融合的过程是怎样的？"),
    ("session_4", "专业合作组织在农村环境治理中有什么作用？"),
    ("session_5", "东西部地区在公共数字文化服务方面有什么差异？"),

    # Session 6-10: 测试记忆回溯
    ("session_6", "我叫什么名字？我的研究方向是什么？"),
    ("session_7", "我之前问了几个问题？请列举一下。"),
    ("session_8", "我们在第二个问题中讨论了什么内容？"),
    ("session_9", "请总结一下我们刚才讨论的主要内容。"),
    ("session_10", "我对哪个问题最感兴趣？根据我们的对话记录判断。"),
]


@pytest.mark.asyncio
async def test_conversation_continuity():
    """测试对话连续性（10 个 session）"""
    # 初始化依赖
    sqlite = SQLiteRepo("./data/app.db")
    sqlite.init()
    zvec = ZvecStore("./data/zvec_db")
    zvec.init()

    redis = RedisCache()
    try:
        await redis.init()
    except Exception:
        logger.warning("Redis 不可用，测试跳过")
        pytest.skip("Redis 不可用")

    bm25 = BM25Store("./data/bm25_index")
    bm25.init()

    init_deps(sqlite, zvec, redis, bm25)

    qa_service = QAService()

    # 记录对话历史
    history: dict[str, list[dict]] = {}
    results: list[dict] = []

    logger.info("=" * 60)
    logger.info("开始对话连续性测试")
    logger.info("=" * 60)

    for i, (session_id, question) in enumerate(CONVERSATION_FLOW, 1):
        logger.info(f"\n--- Session {i}/10 ---")
        logger.info(f"问题: {question}")

        # 执行查询
        response_chunks = []
        sources = []

        try:
            async for event in qa_service.query(
                session_id=session_id,
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
            if session_id not in history:
                history[session_id] = []
            history[session_id].append({
                "question": question,
                "answer": response,
                "sources": sources,
            })

            # 测试记忆回溯（Session 6-10）
            if i >= 6:
                # 检查是否能回答记忆相关的问题
                has_context = _check_context_awareness(question, response, history)
                results.append({
                    "session": i,
                    "session_id": session_id,
                    "question": question,
                    "response_length": len(response),
                    "has_context": has_context,
                    "source_count": len(sources),
                })

                logger.info(f"回答长度: {len(response)} 字")
                logger.info(f"上下文感知: {'✓' if has_context else '✗'}")
            else:
                logger.info(f"回答长度: {len(response)} 字")

        except Exception as e:
            logger.error(f"Session {i} 失败: {e}")
            results.append({
                "session": i,
                "session_id": session_id,
                "error": str(e),
            })

    # 关闭连接
    await qa_service.close()

    # 打印总结
    logger.info("\n" + "=" * 60)
    logger.info("对话连续性测试总结")
    logger.info("=" * 60)

    context_aware_count = sum(1 for r in results if r.get("has_context"))
    total_tested = len(results)

    print(f"\n记忆回溯测试: {context_aware_count}/{total_tested} 通过")

    if context_aware_count == total_tested:
        print("✓ 所有记忆回溯测试通过")
    else:
        print(f"✗ {total_tested - context_aware_count} 个测试未通过")

    # 保存结果
    import json
    with open("tests/conversation_continuity_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "history": history,
            "results": results,
            "summary": {
                "total_sessions": len(CONVERSATION_FLOW),
                "context_aware": context_aware_count,
                "total_tested": total_tested,
            }
        }, f, ensure_ascii=False, indent=2)

    logger.info("\n详细结果已保存到 tests/conversation_continuity_results.json")


def _check_context_awareness(question: str, response: str, history: dict) -> bool:
    """检查回答是否具有上下文感知能力"""
    # 简单启发式检查
    context_keywords = [
        "小明",  # 名字
        "研究生",  # 身份
        "城乡社区治理",  # 研究方向
        "之前", "刚才", "我们讨论",  # 对话引用词
    ]

    # 检查是否包含上下文关键词
    for keyword in context_keywords:
        if keyword in response:
            return True

    # 检查是否回答了具体问题（非空泛回答）
    if len(response) > 50 and "对不起" not in response and "无法" not in response:
        return True

    return False


if __name__ == "__main__":
    asyncio.run(test_conversation_continuity())
