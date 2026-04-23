"""RAG 问答服务（Dense + BM25 混合检索 + RRF 融合 + LLM 流式）"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from app.api.v1.deps import get_bm25, get_redis, get_sqlite, get_zvec
from app.clients.embedding_client import EmbeddingClient
from app.clients.llm_client import LLMClient
from app.pipelines.ingestion.chunker import estimate_tokens

logger = logging.getLogger("paper-assistant")

_SYSTEM_PROMPT = """你是一个学术论文研究助手。你的职责是：
1. 基于提供的参考文献片段，准确回答用户关于论文内容的问题
2. 回答时引用来源（标注论文标题和页码）
3. 如果参考内容不足以回答问题，坦诚说明
4. 使用中文回答

参考文献片段：
{context}"""

_MAX_CONTEXT_TOKENS = 30000
_RRF_K = 60  # RRF 融合常数


def _rrf_fuse(
    dense_results: list,       # list[Doc]，Zvec 返回
    sparse_results: list,      # list[tuple[str, float]]，BM25 返回
    topk: int = 10,
) -> list:
    """RRF 融合 Dense + Sparse 检索结果，返回融合后 topk 的 Doc 列表"""
    # Dense rank 映射: doc_id -> (rank, Doc)
    dense_map: dict[str, tuple[int, object]] = {}
    for rank, doc in enumerate(dense_results, start=1):
        doc_id = doc.id if hasattr(doc, "id") else str(rank)
        dense_map[doc_id] = (rank, doc)

    # Sparse rank 映射: doc_id -> rank
    sparse_map: dict[str, int] = {}
    for rank, (doc_id, _score) in enumerate(sparse_results, start=1):
        sparse_map[doc_id] = rank

    # 计算融合分数
    fused_scores: dict[str, float] = {}
    for doc_id in dense_map:
        score = 1.0 / (_RRF_K + dense_map[doc_id][0])
        if doc_id in sparse_map:
            score += 1.0 / (_RRF_K + sparse_map[doc_id])
        fused_scores[doc_id] = score

    # BM25 独有结果也加入（但没有 Doc 对象，暂不处理内容）
    # 最终只返回有 Doc 对象的结果

    # 按融合分数排序
    sorted_ids = sorted(fused_scores, key=lambda x: fused_scores[x], reverse=True)

    results = []
    for doc_id in sorted_ids[:topk]:
        _, doc = dense_map[doc_id]
        results.append(doc)
    return results


class QAService:
    def __init__(self):
        self._llm = LLMClient()
        self._embedding = EmbeddingClient()

    async def query(
        self,
        session_id: str,
        prompt: str,
        selection: str = "",
        draft: str = "",
        paper_ids: list[str] | None = None,
    ) -> AsyncIterator[dict]:
        """流式问答，yield SSE 事件"""
        # 1. 构建查询
        query_text = prompt
        if selection:
            query_text = f"{prompt}\n\n用户圈选的文本：{selection}" if prompt else selection
        if draft:
            query_text = f"{query_text}\n\n用户已写内容：{draft}" if query_text else draft

        if not query_text:
            yield {"event": "error", "data": {"message": "请提供问题或内容"}}
            return

        # 2. Dense 检索
        try:
            query_vec = await self._embedding.embed_single(query_text)
        except Exception as e:
            logger.error("Embedding 失败: %s", e)
            yield {"event": "error", "data": {"message": "向量化服务暂时不可用"}}
            return

        zvec = get_zvec()
        dense_results = zvec.query(query_vec, topk=20)

        # 3. BM25 检索 + RRF 融合
        try:
            bm25 = get_bm25()
            sparse_results = bm25.query(query_text, topk=20)
            results = _rrf_fuse(dense_results, sparse_results, topk=10)
            logger.info("检索: dense=%d, bm25=%d, 融合后=%d", len(dense_results), len(sparse_results), len(results))
        except Exception as e:
            logger.warning("BM25 检索失败，降级为纯 Dense: %s", e)
            results = dense_results[:10]

        if not results:
            yield {
                "event": "metadata",
                "data": {"session_id": session_id, "source_count": 0, "sources": []},
            }
            async for chunk in self._llm.chat_stream(
                [{"role": "user", "content": query_text}]
            ):
                yield {"event": "chunk", "data": {"content": chunk}}
            yield {"event": "done", "data": {}}
            return

        # 4. 拼装上下文
        context_parts: list[str] = []
        sources: list[dict] = []
        total_tokens = 0

        # 批量查询 paper_id → title 映射
        paper_ids_seen: set[str] = set()
        for doc in results:
            fields = doc.fields if hasattr(doc, "fields") else {}
            pid = fields.get("paper_id", "") if isinstance(fields, dict) else ""
            if pid:
                paper_ids_seen.add(pid)

        paper_titles: dict[str, str] = {}
        if paper_ids_seen:
            try:
                sqlite = get_sqlite()
                with sqlite.get_session() as session:
                    from sqlalchemy import text as sa_text
                    result = session.execute(
                        sa_text("SELECT paper_id, title FROM papers WHERE paper_id IN :ids"),
                        {"ids": tuple(paper_ids_seen)},
                    )
                    for row in result:
                        paper_titles[row[0]] = row[1]
            except Exception as e:
                logger.warning("查询论文标题失败: %s", e)

        for doc in results:
            fields = doc.fields if hasattr(doc, "fields") else {}
            content = fields.get("content", "") if isinstance(fields, dict) else ""
            if not content:
                content = getattr(doc, "content", "")

            tokens = estimate_tokens(content)
            if total_tokens + tokens > _MAX_CONTEXT_TOKENS:
                break

            pid = fields.get("paper_id", "") if isinstance(fields, dict) else ""
            source_info = {
                "paper_id": pid,
                "title": paper_titles.get(pid, ""),
                "page": fields.get("source_page", 0) if isinstance(fields, dict) else 0,
                "section": fields.get("section_title", "") if isinstance(fields, dict) else "",
            }
            sources.append(source_info)
            context_parts.append(
                f"[来源: 论文 {source_info['paper_id'][:8]}, 第{source_info['page']}页]\n{content}"
            )
            total_tokens += tokens

        context = "\n\n---\n\n".join(context_parts)
        logger.info("上下文: %d sources, %d tokens", len(sources), total_tokens)

        # 5. 构建消息
        system_msg = _SYSTEM_PROMPT.format(context=context)
        messages = [{"role": "system", "content": system_msg}]

        # 加载对话历史
        try:
            redis = get_redis()
            history = await redis.get_messages(session_id, limit=20)
            for msg in history[-10:]:
                if msg.get("role") in ("user", "assistant"):
                    messages.append({"role": msg["role"], "content": msg["content"]})
        except Exception:
            pass

        messages.append({"role": "user", "content": query_text})

        # 6. 发送 metadata + 流式 chunk
        yield {
            "event": "metadata",
            "data": {
                "session_id": session_id,
                "source_count": len(sources),
                "sources": sources,
            },
        }

        full_response: list[str] = []
        try:
            async for chunk in self._llm.chat_stream(messages):
                full_response.append(chunk)
                yield {"event": "chunk", "data": {"content": chunk}}
        except Exception as e:
            logger.error("LLM 流式调用失败: %s", e)
            yield {"event": "error", "data": {"message": "LLM 服务暂时不可用"}}

        # 7. 保存对话历史
        if full_response:
            try:
                redis = get_redis()
                await redis.add_message(session_id, {"role": "user", "content": query_text})
                await redis.add_message(
                    session_id, {"role": "assistant", "content": "".join(full_response)}
                )
            except Exception:
                pass

        yield {"event": "done", "data": {}}

    async def close(self) -> None:
        await self._llm.close()
        await self._embedding.close()
