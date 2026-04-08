"""PDF 导入工作流.

完整流程：
MinerU 解析 → 清洗 → VLM 图片描述 → 混合切分 → Embedding → Qdrant 存储
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.clients.mineru_client import MinerUClient
from app.core.config import get_settings
from app.models.base import Chunk
from app.processing.cleaner import clean_paper
from app.processing.describer import describe_chunks
from app.processing.chunker import SemanticChunk, chunk_by_semantic_units
from app.services.embedding_service import EmbeddingService
from app.stores.qdrant_store import QdrantStore

settings = get_settings()


class IngestWorkflow:
    """PDF 导入工作流."""

    def __init__(
        self,
        mineru_client: MinerUClient | None = None,
        embedding_service: EmbeddingService | None = None,
        qdrant_store: QdrantStore | None = None,
    ):
        """初始化工作流.

        Args:
            mineru_client: MinerU 客户端
            embedding_service: Embedding 服务
            qdrant_store: Qdrant 存储
        """
        self.mineru_client = mineru_client or MinerUClient()
        self.embedding_service = embedding_service or EmbeddingService()
        self.qdrant_store = qdrant_store or QdrantStore()

    async def ingest_pdf(
        self,
        pdf_path: Path,
        paper_id: str | None = None,
    ) -> dict[str, Any]:
        """完整导入单个 PDF.

        Args:
            pdf_path: PDF 文件路径
            paper_id: 论文 ID（可选，默认从文件名提取）

        Returns:
            导入结果统计
        """
        pdf_path = Path(pdf_path)
        if paper_id is None:
            paper_id = pdf_path.stem

        print(f"📄 开始导入: {pdf_path.name}")

        # 阶段1: MinerU 解析
        print(f"   1. MinerU 解析...")
        extract_dir = self.mineru_client.parse_pdf(pdf_path)
        print(f"      ✅ 解析完成: {extract_dir}")

        # 阶段2: 清洗
        print(f"   2. 清洗数据...")
        chunks = clean_paper(extract_dir, paper_id)
        print(f"      ✅ 清洗完成: {len(chunks)} chunks")

        # 阶段3: VLM 图片描述
        image_count = sum(1 for c in chunks if c.image_path)
        if image_count > 0:
            print(f"   3. VLM 图片描述 ({image_count} images)...")
            chunks = await describe_chunks(extract_dir, chunks)
            print(f"      ✅ 描述完成")
        else:
            print(f"   3. VLM 图片描述 (跳过，无图片)")

        # 阶段4: 混合切分
        print(f"   4. 混合切分...")
        semantic_chunks = [
            SemanticChunk(
                content=c.content,
                section=c.section,
                metadata={"chunk_type": c.chunk_type, "image_path": c.image_path},
            )
            for c in chunks
        ]
        text_chunks = chunk_by_semantic_units(semantic_chunks)
        print(f"      ✅ 切分完成: {len(text_chunks)} text chunks")

        # 转换回 Chunk 格式
        final_chunks = [
            Chunk(
                id=f"{paper_id}_chunk{i:04d}",
                paper=paper_id,
                chunk_type=tc.metadata.get("chunk_type", "text"),
                content=tc.content,
                section=tc.section,
                image_path=tc.metadata.get("image_path"),
                metadata=tc.metadata,
            )
            for i, tc in enumerate(text_chunks)
        ]

        # 阶段5: Embedding
        print(f"   5. Embedding ({len(final_chunks)} chunks)...")
        embeddings = await self.embedding_service.embed_texts_async(
            [c.content for c in final_chunks]
        )
        print(f"      ✅ Embedding 完成: {len(embeddings)} vectors")

        # 阶段6: Qdrant 存储
        print(f"   6. Qdrant 存储...")
        self.qdrant_store.add_chunks(paper_id, final_chunks, embeddings)
        print(f"      ✅ 存储完成")

        return {
            "paper_id": paper_id,
            "extract_dir": str(extract_dir),
            "chunks_count": len(final_chunks),
            "vector_dimension": len(embeddings[0]) if embeddings else 0,
        }

    async def batch_ingest(
        self,
        pdf_paths: list[Path],
        continue_on_error: bool = True,
    ) -> dict[str, Any]:
        """批量导入 PDF.

        Args:
            pdf_paths: PDF 文件路径列表
            continue_on_error: 失败时是否继续

        Returns:
            批量导入结果
        """
        results = {
            "success": [],
            "failed": [],
            "total": len(pdf_paths),
        }

        for i, pdf_path in enumerate(pdf_paths, 1):
            print(f"\n[{i}/{len(pdf_paths)}] {pdf_path.name}")

            try:
                result = await self.ingest_pdf(pdf_path)
                results["success"].append({
                    "paper_id": result["paper_id"],
                    "source": str(pdf_path),
                    "chunks_count": result["chunks_count"],
                })
            except Exception as e:
                print(f"   ❌ 失败: {e}")
                results["failed"].append({
                    "source": str(pdf_path),
                    "error": str(e),
                })

                if not continue_on_error:
                    break

        print(f"\n✅ 批量导入完成:")
        print(f"   成功: {len(results['success'])}")
        print(f"   失败: {len(results['failed'])}")

        return results

    def get_status(self) -> dict[str, Any]:
        """获取当前状态."""
        papers = self.qdrant_store.list_papers()
        return {
            "papers_count": len(papers),
            "total_chunks": self.qdrant_store.count,
            "papers": papers,
        }
