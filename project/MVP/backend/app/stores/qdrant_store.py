"""Qdrant 向量库存储.

每篇论文独立 collection，支持分布式隔离管理。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
    Filter,
    FieldCondition,
    MatchValue,
)

from app.core.config import get_settings
from app.models.base import Chunk

settings = get_settings()


def _get_collection_name(paper_id: str) -> str:
    """获取 collection 名称（合法化处理）."""
    # Qdrant collection 名称限制：只能包含字母、数字、下划线、连字符
    name = f"paper_{paper_id}".replace("-", "_").replace(" ", "_")
    # 移除非法字符
    import re

    name = re.sub(r"[^a-zA-Z0-9_-]", "", name)
    return name.lower()


class QdrantStore:
    """Qdrant 向量库存储."""

    def __init__(
        self,
        path: str | None = None,
        url: str | None = None,
        api_key: str | None = None,
    ):
        """初始化 Qdrant 客户端.

        Args:
            path: 本地存储路径（默认使用配置）
            url: 远程服务 URL（可选）
            api_key: API Key（远程时需要）
        """
        self.path = path or settings.qdrant_path
        self.url = url or settings.qdrant_url or None
        self.api_key = api_key or settings.qdrant_api_key or None

        if self.url:
            self.client = QdrantClient(url=self.url, api_key=self.api_key)
        else:
            Path(self.path).mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=self.path)

    def create_paper_collection(
        self,
        paper_id: str,
        vector_size: int,
    ) -> None:
        """为论文创建独立 collection.

        Args:
            paper_id: 论文 ID
            vector_size: 向量维度
        """
        collection_name = _get_collection_name(paper_id)

        # 检查是否已存在
        collections = self.client.get_collections().collections
        existing = {c.name for c in collections}

        if collection_name in existing:
            # 已存在，检查维度是否匹配
            info = self.client.get_collection(collection_name)
            if info.config.params.vectors.size != vector_size:
                raise ValueError(
                    f"Collection {collection_name} exists with "
                    f"dimension {info.config.params.vectors.size}, "
                    f"but got {vector_size}"
                )
            return

        # 创建新 collection
        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            ),
        )

    def add_chunks(
        self,
        paper_id: str,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> None:
        """添加 chunks 到 collection.

        Args:
            paper_id: 论文 ID
            chunks: Chunk 列表
            embeddings: 向量列表
        """
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have same length")

        collection_name = _get_collection_name(paper_id)

        # 确保 collection 存在
        vector_size = len(embeddings[0]) if embeddings else settings.embedding_dimensions
        self.create_paper_collection(paper_id, vector_size)

        # 构建点
        points = [
            PointStruct(
                id=chunk.id,
                vector=embedding,
                payload={
                    "content": chunk.content,
                    "section": chunk.section,
                    "page": chunk.page,
                    "image_path": chunk.image_path or "",
                    "chunk_type": chunk.chunk_type,
                    "paper": chunk.paper,
                },
            )
            for chunk, embedding in zip(chunks, embeddings)
        ]

        # 批量上传
        self.client.upsert(
            collection_name=collection_name,
            points=points,
        )

    def search(
        self,
        paper_id: str,
        query_vector: list[float],
        limit: int = 10,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """在指定论文中搜索.

        Args:
            paper_id: 论文 ID
            query_vector: 查询向量
            limit: 返回数量
            score_threshold: 相似度阈值

        Returns:
            搜索结果列表
        """
        collection_name = _get_collection_name(paper_id)

        results = self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
        )

        return [
            {
                "id": r.id,
                "score": r.score,
                "payload": r.payload,
            }
            for r in results
        ]

    def search_all(
        self,
        query_vector: list[float],
        limit: int = 10,
        paper_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """在所有论文中搜索.

        Args:
            query_vector: 查询向量
            limit: 每篇论文返回数量
            paper_filter: 限制搜索到指定论文

        Returns:
            搜索结果列表
        """
        collections = self.client.get_collections().collections
        all_results: list[dict[str, Any]] = []

        for collection in collections:
            # 过滤论文
            paper_id = collection.name.replace("paper_", "")
            if paper_filter and paper_id != paper_filter:
                continue

            # 在该论文中搜索
            try:
                results = self.search(
                    paper_id=paper_id,
                    query_vector=query_vector,
                    limit=limit,
                )
                all_results.extend(results)
            except Exception:
                # collection 可能不存在或为空
                continue

        # 按分数排序
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:limit]

    def delete_paper(self, paper_id: str) -> None:
        """删除论文的 collection.

        Args:
            paper_id: 论文 ID
        """
        collection_name = _get_collection_name(paper_id)

        try:
            self.client.delete_collection(collection_name)
        except Exception:
            # collection 可能不存在
            pass

    def get_paper_info(self, paper_id: str) -> dict[str, Any] | None:
        """获取论文 collection 信息.

        Args:
            paper_id: 论文 ID

        Returns:
            Collection 信息，不存在返回 None
        """
        collection_name = _get_collection_name(paper_id)

        try:
            info = self.client.get_collection(collection_name)
            return {
                "name": info.config.params.vectors,
                "points_count": info.points_count,
                "vector_size": info.config.params.vectors.size,
            }
        except Exception:
            return None

    def list_papers(self) -> list[str]:
        """列出所有已入库的论文.

        Returns:
            论文 ID 列表
        """
        collections = self.client.get_collections().collections
        return [
            c.name.replace("paper_", "")
            for c in collections
            if c.name.startswith("paper_")
        ]

    @property
    def count(self) -> int:
        """总点数（所有论文合计）."""
        total = 0
        collections = self.client.get_collections().collections

        for collection in collections:
            try:
                info = self.client.get_collection(collection.name)
                total += info.points_count
            except Exception:
                continue

        return total
