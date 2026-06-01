"""兼容版 AnswerGenerator。

保留旧测试和旧调用点所需的流式生成接口，但内部只依赖当前的
检索、source mapping 和 conversation repo，不再回到旧的 service 层。
"""

from __future__ import annotations

import inspect
import json
from datetime import datetime, timezone
from typing import Any

from app.agent_layer.response.source_mapper import map_sources
from app.data_layer.indexing.chroma_store.keyword_index import KeywordIndex
from app.data_layer.indexing.chroma_store.vector_index import VectorIndex
from app.data_layer.retrieval import fusion

_SYSTEM_PROMPT = "你是一个有帮助的学术写作助手。请用中文回答用户的问题。"


class AnswerGenerator:
    def __init__(
        self,
        settings: Any,
        chat_model: Any,
        vector_store: Any,
        keyword_search: Any,
        conversation_repo: Any,
        embedding_client: Any | None = None,
    ) -> None:
        self._settings = settings
        self._chat_model = chat_model
        self._vector_store = vector_store
        self._keyword_search = keyword_search
        self._conversation_repo = conversation_repo
        self._embedding_client = embedding_client

    async def generate(self, session_id: str, query: str):
        if not query or not query.strip():
            yield {"event": "error", "data": {"message": "请提供问题或内容"}}
            return

        retrieval_results = await self._retrieve(query)
        sources = map_sources(retrieval_results)

        yield {
            "event": "metadata",
            "data": {
                "session_id": session_id,
                "source_count": len(sources),
                "sources": [source.model_dump() for source in sources],
            },
        }

        if not sources:
            yield {
                "event": "chunk",
                "data": {"content": "未找到相关文献。"},
            }
            yield {"event": "done", "data": {"session_id": session_id}}
            return

        messages = self._build_messages(session_id, query, sources)
        answer = ""

        try:
            stream = self._chat_model.chat_stream(messages)
            if inspect.isawaitable(stream):
                stream = await stream

            async for chunk in stream:
                if not chunk:
                    continue
                answer += chunk
                yield {"event": "chunk", "data": {"content": chunk}}
        except Exception as exc:
            yield {
                "event": "error",
                "data": {
                    "message": "生成回答失败",
                    "detail": str(exc),
                    "session_id": session_id,
                },
            }
            return

        await self._persist_turn(session_id, query, answer, sources)
        yield {"event": "done", "data": {"session_id": session_id}}

    async def _retrieve(self, query: str) -> list[dict]:
        dense_results = []
        sparse_results = []

        if self._embedding_client is not None and self._vector_store is not None:
            try:
                query_vector = await self._embedding_client.embed_single(query)
                result = self._vector_store.query(query_vector, topk=20)
                if isinstance(result, list):
                    dense_results = result
            except Exception:
                pass

        if self._keyword_search is not None:
            try:
                result = self._keyword_search.query(query, topk=20)
                if isinstance(result, list):
                    sparse_results = result
            except Exception:
                pass

        fused = fusion.rrf_fuse(
            dense_results,
            sparse_results,
            topk=10,
            keyword_index=self._keyword_search,
            rrf_k=self._settings.retrieval_rrf_k,
        )
        results: list[dict] = []
        for doc in fused:
            content = ""
            metadata: dict[str, Any] = {}
            if hasattr(doc, "fields"):
                content = doc.fields.get("content", "")
                metadata = {k: v for k, v in doc.fields.items() if k != "content"}
            elif hasattr(doc, "content"):
                content = doc.content
                metadata = getattr(doc, "metadata", {}) or {}

            results.append(
                {
                    "content": content,
                    "paper_id": metadata.get("paper_id", ""),
                    "chunk_id": metadata.get("chunk_id", doc.id),
                    "title": metadata.get("section_title", ""),
                    "page": metadata.get("source_page"),
                    "section": metadata.get("section_title", ""),
                    "anchor_id": metadata.get("anchor_id", ""),
                    "chunk_index": metadata.get("chunk_index"),
                }
            )
        return results

    def _build_messages(self, session_id: str, query: str, sources: list) -> list[dict]:
        messages = [{"role": "system", "content": _SYSTEM_PROMPT}]

        history = self._read_history(session_id)
        messages.extend(history[-10:])

        source_lines: list[str] = []
        for idx, source in enumerate(sources, start=1):
            title = source.title or "未命名论文"
            section = source.section or ""
            content = source.content or ""
            source_lines.append(f"[{idx}] {title} {section} {content}".strip())

        if source_lines:
            messages.append(
                {
                    "role": "system",
                    "content": "参考资料：\n" + "\n".join(source_lines),
                }
            )

        messages.append({"role": "user", "content": query})
        return messages

    def _read_history(self, session_id: str) -> list[dict]:
        if not hasattr(self._conversation_repo, "get_messages"):
            return []

        try:
            raw_messages = self._conversation_repo.get_messages(session_id)
        except Exception:
            return []

        history: list[dict] = []
        for msg in raw_messages or []:
            role = getattr(msg, "role", None)
            content = getattr(msg, "content", None)
            if role is None and isinstance(msg, dict):
                role = msg.get("role")
                content = msg.get("content")
            if role and content:
                history.append({"role": role, "content": content})
        return history

    async def _persist_turn(self, session_id: str, query: str, answer: str, sources: list) -> None:
        if not hasattr(self._conversation_repo, "save_message"):
            return

        sources_json = json.dumps(
            [source.model_dump() for source in sources],
            ensure_ascii=False,
        )

        user_msg = {
            "session_id": session_id,
            "role": "user",
            "content": query,
            "created_at": self._utc_now(),
            "sources_json": None,
        }
        assistant_msg = {
            "session_id": session_id,
            "role": "assistant",
            "content": answer,
            "created_at": self._utc_now(),
            "sources_json": sources_json,
        }

        for payload in (user_msg, assistant_msg):
            try:
                self._conversation_repo.save_message(payload)
            except TypeError:
                try:
                    self._conversation_repo.save_message(**payload)
                except Exception:
                    pass
            except Exception:
                pass

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()


__all__ = ["AnswerGenerator", "KeywordIndex", "VectorIndex"]
