# BM25 仓储
# 这里同时承担两类职责：
# 1. 作为关键词检索索引
# 2. 作为 parent_child 的最小块元数据存储
#
# 设计上把“所有块”都存起来，但只让 searchable=True 的块参与检索。
# 这样 parent_child 模式下：
# - 子块参与召回
# - 父块只负责回挂展示
# - 删除文档时两类块都能一起清掉

from __future__ import annotations

import os
import pickle
import re
from pathlib import Path

import jieba
from rank_bm25 import BM25Okapi

from app.core.config import get_settings
from app.modules.indexing.dto import BM25SearchHit, IndexedChunk

# 这类 token 常见于文档块 ID、文件名片段、slug。
# Task 5 的关键问题在于：
# - 文档侧把它当成一个完整 token
# - 查询侧却被 jieba 拆碎
# 所以这里先把这类 ASCII 标识符整体保留，保证 query/document 分词一致。
_ID_STYLE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class BM25Repo:
    """最小 BM25 仓储。"""

    def __init__(self) -> None:
        settings = get_settings()
        self._index_path = Path(settings.bm25_index_path)
        self._all_chunks: list[IndexedChunk] = []
        self._searchable_chunks: list[IndexedChunk] = []
        self._searchable_tokens: list[list[str]] = []
        self._bm25: BM25Okapi | None = None
        self._pending_save_chunks: list[IndexedChunk] | None = None

        if self._index_path.exists():
            self.load()
        else:
            self._rebuild_search_index()

    def upsert_chunks(self, chunks: list[IndexedChunk]) -> int:
        """批量写入或更新 BM25 块。"""
        if not chunks:
            return 0

        upsert_ids = {chunk.chunk_id for chunk in chunks}
        remained_chunks = [chunk for chunk in self._all_chunks if chunk.chunk_id not in upsert_ids]
        staged_chunks = remained_chunks + list(chunks)

        # 这里必须先持久化 staged 快照，再切换内存态。
        # 否则一旦 save() 失败，内存中的旧索引会先被覆盖，服务层即使想补偿也拿不到旧 BM25 状态。
        self._save_staged_chunks(staged_chunks)
        self._all_chunks = staged_chunks
        self._rebuild_search_index()
        return len(chunks)

    def query(self, query_text: str, top_k: int = 30) -> list[BM25SearchHit]:
        """执行 BM25 查询，只返回 searchable=True 的块。"""
        if not self._bm25 or not self._searchable_chunks:
            return []

        query_tokens = self._tokenize_text(query_text)
        if not query_tokens:
            return []

        scores = self._bm25.get_scores(query_tokens)
        ranked_pairs = sorted(
            enumerate(scores),
            key=lambda item: float(item[1]),
            reverse=True,
        )

        results: list[BM25SearchHit] = []
        for index, score in ranked_pairs:
            numeric_score = float(score)
            if numeric_score <= 0:
                continue
            chunk = self._searchable_chunks[index]
            results.append(
                BM25SearchHit(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    text=chunk.text,
                    score=numeric_score,
                    node_kind=chunk.node_kind,
                    searchable=chunk.searchable,
                    parent_chunk_id=chunk.parent_chunk_id,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                )
            )
            if len(results) >= top_k:
                break

        return results

    def get_chunks_by_ids(self, chunk_ids: list[str]) -> list[IndexedChunk]:
        """按 ID 取块，保持输入顺序。"""
        if not chunk_ids:
            return []
        chunk_map = {chunk.chunk_id: chunk for chunk in self._all_chunks}
        return [chunk_map[chunk_id] for chunk_id in chunk_ids if chunk_id in chunk_map]

    def count(self, document_id: str | None = None, *, searchable_only: bool = False) -> int:
        """统计块数量。"""
        target_chunks = self._searchable_chunks if searchable_only else self._all_chunks
        if document_id is None:
            return len(target_chunks)
        return sum(1 for chunk in target_chunks if chunk.document_id == document_id)

    def delete_document(self, document_id: str) -> int:
        """删除某个文档的全部 BM25 条目。"""
        original_count = len(self._all_chunks)
        staged_chunks = [chunk for chunk in self._all_chunks if chunk.document_id != document_id]
        deleted_count = original_count - len(staged_chunks)
        if deleted_count == 0:
            return 0

        # 删除也必须走 staged 快照。
        # 本质上“删除旧索引”也是一次状态替换，如果 save() 失败就绝不能把旧内存态提前删掉。
        self._save_staged_chunks(staged_chunks)
        self._all_chunks = staged_chunks
        self._rebuild_search_index()
        return deleted_count

    def save(self) -> None:
        """持久化到本地文件。

        这里改成原子写，原因是普通直接覆盖会暴露一个致命窗口：
        1. 进程刚把目标文件截断
        2. 还没完整写完就异常退出
        3. 下次启动只能读到半截 pickle，直接触发 UnpicklingError

        临时文件 + replace 的本质，是把“写入中间态”藏在旁路文件里，
        只有完整写成功后，才一次性替换正式索引文件。
        """
        target_chunks = self._pending_save_chunks if self._pending_save_chunks is not None else self._all_chunks
        self._index_path.parent.mkdir(parents=True, exist_ok=True)

        temp_path = self._index_path.with_name(f"{self._index_path.name}.tmp")
        with temp_path.open("wb") as file:
            pickle.dump([chunk.model_dump() for chunk in target_chunks], file)
            file.flush()
            os.fsync(file.fileno())

        temp_path.replace(self._index_path)

    def snapshot(self) -> list[IndexedChunk]:
        """返回当前 BM25 全量块快照。

        这里返回新 list，目的是让服务层拿到一个稳定副本，
        后续即使仓储内部发生 staged 替换，也不会把外部持有的旧快照一起污染。
        """
        return list(self._all_chunks)

    def restore(self, chunks: list[IndexedChunk]) -> int:
        """把旧快照恢复成当前 BM25 状态。"""
        self._save_staged_chunks(list(chunks))
        self._all_chunks = list(chunks)
        self._rebuild_search_index()
        return len(chunks)

    def load(self) -> None:
        """从本地文件恢复。

        向后兼容策略：
        1. 新格式要求磁盘里是 list[chunk_dict]。
        2. 如果读到旧版 dict schema（如 corpus/tokenized/doc_ids），说明它不再可直接恢复。
        3. 如果文件损坏、截断、内容非法，也不应该让初始化直接崩溃。
        4. 这几类场景的最小可接受行为，都是降级为空索引并等待后续重建。
        """
        try:
            with self._index_path.open("rb") as file:
                raw_chunks = pickle.load(file)
        except (pickle.PickleError, EOFError, ValueError, TypeError, AttributeError):
            self._all_chunks = []
            self._rebuild_search_index()
            return

        if self._is_legacy_payload(raw_chunks):
            self._all_chunks = []
            self._rebuild_search_index()
            return

        if not isinstance(raw_chunks, list):
            self._all_chunks = []
            self._rebuild_search_index()
            return

        try:
            self._all_chunks = [IndexedChunk.model_validate(raw_chunk) for raw_chunk in raw_chunks]
        except Exception:
            # 这里兜底处理“pickle 能读出来，但内部结构不是合法 chunk 列表”的坏数据。
            # 本质上这和坏文件一样，都是无法安全恢复，因此直接降级为空索引。
            self._all_chunks = []
        self._rebuild_search_index()

    def _rebuild_search_index(self) -> None:
        """根据当前块列表重建 BM25 检索结构。"""
        self._searchable_chunks = [chunk for chunk in self._all_chunks if chunk.searchable]
        self._searchable_tokens = [self._tokenize_text(chunk.text) for chunk in self._searchable_chunks]
        if self._searchable_tokens:
            self._bm25 = BM25Okapi(self._searchable_tokens)
        else:
            self._bm25 = None

    def _save_staged_chunks(self, chunks: list[IndexedChunk]) -> None:
        """持久化一份待切换的 staged 快照。

        这里故意复用 save()，而不是再复制一份写文件逻辑，
        这样测试里只要覆写 save()，就能稳定模拟真实持久化失败。
        """
        self._pending_save_chunks = chunks
        try:
            self.save()
        finally:
            self._pending_save_chunks = None

    @staticmethod
    def _is_legacy_payload(raw_payload: object) -> bool:
        """判断是否为旧版 BM25 持久化 schema。

        旧格式是独立维护的 BM25 结构，核心特征是顶层为 dict，
        并包含 corpus/tokenized/doc_ids 这类字段，而不是 chunk 列表。
        这里只做最小识别，不尝试迁移旧数据，避免把兼容逻辑扩散成新需求。
        """
        return isinstance(raw_payload, dict) and {"corpus", "tokenized", "doc_ids"}.issubset(raw_payload.keys())

    @staticmethod
    def _tokenize_text(text: str) -> list[str]:
        """做一个对中英文都尽量稳妥的最小分词。

        规则：
        1. 先去掉首尾空白，空文本直接返回空列表。
        2. 如果文本里存在空白，就先按空白切，再对每个片段做统一分词。
           这样文档侧和查询侧都会走同一套规则，而不是“一边 split、一边 jieba”。
        3. 对 doc-write-delete_p1_0001 这类 ID 风格 token，整体保留。
        4. 其他连续文本再退回 jieba，兼容普通中文检索。
        """
        stripped_text = text.strip()
        if not stripped_text:
            return []

        if any(character.isspace() for character in stripped_text):
            tokens: list[str] = []
            for raw_token in stripped_text.split():
                tokens.extend(BM25Repo._tokenize_non_whitespace_text(raw_token))
            return tokens

        return BM25Repo._tokenize_non_whitespace_text(stripped_text)

    @staticmethod
    def _tokenize_non_whitespace_text(text: str) -> list[str]:
        """对不含空白的片段做统一分词。

        先识别并整体保留 ID 风格 token，
        否则再交给 jieba 处理自然语言文本。
        """
        if _ID_STYLE_TOKEN_PATTERN.fullmatch(text):
            return [text]
        return [token.strip() for token in jieba.lcut(text) if token.strip()]
