# 导入工作流
# 协调三阶段：清洗 → 向量化 → 索引
from pathlib import Path
from typing import List, Dict, Optional
from app.services.cleaning_service import CleaningService
from app.services.embedding_service import EmbeddingService
from app.services.indexing_service import IndexingService


class IngestWorkflow:
    """导入工作流，协调三阶段"""

    def __init__(self, cache_dir: str = "./data/cache"):
        self.cleaning_service = CleaningService(Path(cache_dir))
        self.embedding_service = EmbeddingService(self.cleaning_service)
        self.indexing_service = IndexingService(self.cleaning_service)

    async def ingest_single_pdf(
        self,
        pdf_path: str,
        document_id: Optional[str] = None,
    ) -> Dict:
        """
        完整导入单个 PDF（三阶段）

        Args:
            pdf_path: PDF 文件路径
            document_id: 可选的文档 ID

        Returns:
            最终的 JSON 数据
        """
        # 阶段1：清洗
        print(f"📄 清洗: {Path(pdf_path).name}")
        cache_data = self.cleaning_service.clean_pdf(pdf_path, document_id)
        doc_id = cache_data["document_id"]
        print(f"   ✅ 清洗完成，段落: {len(cache_data['paragraphs'])}")

        # 阶段2：向量化
        print(f"🔮 向量化: {doc_id}")
        cache_data = await self.embedding_service.generate_embeddings(doc_id)
        print(f"   ✅ 向量化完成")

        # 阶段3：索引
        print(f"💾 索引入库: {doc_id}")
        result = self.indexing_service.index_document(doc_id)
        print(f"   ✅ 索引完成，向量: {result['vector_count']}, BM25: {result['bm25_count']}")

        return self.cleaning_service.load_cache(doc_id)

    async def batch_ingest(
        self,
        pdf_paths: List[str],
        continue_on_error: bool = True,
    ) -> Dict:
        """
        批量导入 PDF，错误隔离

        Args:
            pdf_paths: PDF 文件路径列表
            continue_on_error: 失败时是否继续

        Returns:
            {
                "success": [{"doc_id", "source"}],
                "failed": [{"source", "error"}],
                "total": int,
            }
        """
        results = {
            "success": [],
            "failed": [],
            "total": len(pdf_paths),
        }

        for i, pdf_path in enumerate(pdf_paths, 1):
            print(f"\n[{i}/{len(pdf_paths)}] 处理: {Path(pdf_path).name}")
            
            try:
                cache_data = await self.ingest_single_pdf(pdf_path)
                results["success"].append({
                    "doc_id": cache_data["document_id"],
                    "source": pdf_path,
                })
            except Exception as e:
                print(f"   ❌ 失败: {e}")
                results["failed"].append({
                    "source": pdf_path,
                    "error": str(e),
                })
                
                if not continue_on_error:
                    break

        print(f"\n✅ 批量导入完成:")
        print(f"   成功: {len(results['success'])}")
        print(f"   失败: {len(results['failed'])}")
        
        return results

    async def resume_ingest(self) -> Dict:
        """
        断点续传：从缓存状态恢复导入

        Returns:
            处理结果统计
        """
        status = self.cleaning_service.get_all_cache_status()
        print(f"📊 缓存状态: {status}")

        results = {
            "cleaned": 0,
            "embedding": 0,
            "failed": 0,
        }

        # 1. 处理 cleaned（向量化）
        cleaned_docs = self.cleaning_service.get_cache_by_status("cleaned")
        for doc_data in cleaned_docs:
            try:
                print(f"🔮 向量化: {doc_data['document_id']}")
                await self.embedding_service.generate_embeddings(doc_data["document_id"])
                results["cleaned"] += 1
            except Exception as e:
                print(f"   ❌ 失败: {e}")

        # 2. 处理 embedding（索引）
        embedding_docs = self.cleaning_service.get_cache_by_status("embedding")
        for doc_data in embedding_docs:
            try:
                print(f"💾 索引: {doc_data['document_id']}")
                self.indexing_service.index_document(doc_data["document_id"])
                results["embedding"] += 1
            except Exception as e:
                print(f"   ❌ 失败: {e}")

        # 3. 重试 failed
        failed_docs = self.cleaning_service.get_cache_by_status("failed")
        for doc_data in failed_docs:
            try:
                print(f"🔄 重试: {doc_data['document_id']}")
                await self.ingest_single_pdf(doc_data["source_file"])
                results["failed"] += 1
            except Exception as e:
                print(f"   ❌ 仍然失败: {e}")

        print(f"\n✅ 续传完成: {results}")
        return results

    def get_status(self) -> Dict:
        """获取当前状态"""
        cache_status = self.cleaning_service.get_all_cache_status()
        return {
            "cache": cache_status,
            "chroma_count": self.indexing_service.chroma_repo.count(),
            "bm25_count": self.indexing_service.bm25_repo.count(),
        }
