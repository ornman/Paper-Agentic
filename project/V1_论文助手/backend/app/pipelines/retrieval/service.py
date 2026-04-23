"""RAG 问答服务（Dense + BM25 混合检索 + RRF 融合 + LLM 流式）"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from app.api.v1.deps import get_bm25, get_sqlite, get_zvec
from app.clients.embedding_client import EmbeddingClient
from app.clients.llm_client import LLMClient
from app.pipelines.ingestion.chunker import estimate_tokens

logger = logging.getLogger("paper-assistant")

_SYSTEM_PROMPT = """你是一个有帮助的助手。请用中文回答用户的问题。

{context}
"""

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
        enable_rag: bool = True,
    ) -> AsyncIterator[dict]:
        """流式问答，yield SSE 事件

        Args:
            enable_rag: 是否启用 RAG 检索。False 时直接调用 LLM，不检索文献
        """
        # 1. 构建查询
        query_text = prompt
        if selection:
            query_text = f"{prompt}\n\n用户圈选的文本：{selection}" if prompt else selection
        if draft:
            query_text = f"{query_text}\n\n用户已写内容：{draft}" if query_text else draft

        if not query_text:
            yield {"event": "error", "data": {"message": "请提供问题或内容"}}
            return

        # 如果禁用 RAG，直接调用 LLM
        if not enable_rag:
            logger.info("RAG 已禁用，直接调用 LLM")
            yield {
                "event": "metadata",
                "data": {"session_id": session_id, "source_count": 0, "sources": []},
            }

            # 加载对话历史
            messages = []
            try:
                sqlite = get_sqlite()
                history = sqlite.get_messages(session_id, limit=20)
                for msg in history[-10:]:
                    if msg.get("role") in ("user", "assistant"):
                        messages.append({"role": msg["role"], "content": msg["content"]})
            except Exception:
                pass

            messages.append({"role": "user", "content": query_text})

            full_response: list[str] = []
            try:
                async for chunk in self._llm.chat_stream(messages):
                    full_response.append(chunk)
                    yield {"event": "chunk", "data": {"content": chunk}}
            except Exception as e:
                logger.error("LLM 流式调用失败: %s", e)
                yield {"event": "error", "data": {"message": "LLM 服务暂时不可用"}}

            # 保存对话历史
            if full_response:
                import time
                now = time.strftime("%Y-%m-%dT%H:%M:%S")
                try:
                    sqlite = get_sqlite()
                    with sqlite.get_session() as session:
                        from sqlalchemy import text as sa_text
                        session.execute(sa_text(
                            "INSERT INTO conversations (session_id, role, content, created_at) "
                            "VALUES (:sid, :role, :content, :time)"
                        ), {"sid": session_id, "role": "user", "content": query_text, "time": now})
                        session.execute(sa_text(
                            "INSERT INTO conversations (session_id, role, content, created_at) "
                            "VALUES (:sid, :role, :content, :time)"
                        ), {"sid": session_id, "role": "assistant", "content": "".join(full_response), "time": now})
                        session.commit()
                except Exception as e:
                    logger.warning("保存对话到 SQLite 失败: %s", e)

            yield {"event": "done", "data": {}}
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
        paper_paths: dict[str, str] = {}
        if paper_ids_seen:
            try:
                sqlite = get_sqlite()
                with sqlite.get_session() as session:
                    from sqlalchemy import text as sa_text, bindparam
                    stmt = sa_text(
                        "SELECT paper_id, title, file_path FROM papers WHERE paper_id IN :ids"
                    ).bindparams(bindparam("ids", expanding=True))
                    result = session.execute(stmt, {"ids": list(paper_ids_seen)})
                    for row in result:
                        paper_titles[row[0]] = row[1]
                        paper_paths[row[0]] = row[2]
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
                "id": f"{pid}_{fields.get('chunk_id', '')}",  # 唯一ID
                "paper_id": pid,
                "title": paper_titles.get(pid, ""),
                "page": fields.get("source_page", 0) if isinstance(fields, dict) else 0,
                "section": fields.get("section_title", "") if isinstance(fields, dict) else "",
                "file_path": paper_paths.get(pid, ""),
                "content": content,  # 完整段落内容
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
            sqlite = get_sqlite()
            history = sqlite.get_messages(session_id, limit=20)
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
            import time
            now = time.strftime("%Y-%m-%dT%H:%M:%S")
            try:
                sqlite = get_sqlite()
                with sqlite.get_session() as session:
                    from sqlalchemy import text as sa_text
                    session.execute(sa_text(
                        "INSERT INTO conversations (session_id, role, content, created_at) "
                        "VALUES (:sid, :role, :content, :time)"
                    ), {"sid": session_id, "role": "user", "content": query_text, "time": now})
                    session.execute(sa_text(
                        "INSERT INTO conversations (session_id, role, content, created_at) "
                        "VALUES (:sid, :role, :content, :time)"
                    ), {"sid": session_id, "role": "assistant", "content": "".join(full_response), "time": now})
                    session.commit()
            except Exception as e:
                logger.warning("保存对话到 SQLite 失败: %s", e)

        yield {"event": "done", "data": {}}

    async def close(self) -> None:
        await self._llm.close()
        await self._embedding.close()

    async def generate_title(self, first_message: str) -> str:
        """根据首条用户消息生成简短对话标题"""
        prompt = (
            "请根据以下用户消息，生成一个简短的对话标题（5-12个汉字）。\n"
            "要求：简洁概括主题，不要加引号或标点。\n\n"
            f"用户消息：{first_message[:200]}\n\n标题："
        )
        response = await self._llm.chat([{"role": "user", "content": prompt}])
        title = response.strip().strip('"\'""''')
        if not title:
            title = first_message[:20]
        return title
