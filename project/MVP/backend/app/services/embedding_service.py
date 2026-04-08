# 向量化服务
# 阶段2：读取 JSON → 批量 Embedding → 更新 JSON
from typing import List, Dict
from app.services.cleaning_service import CleaningService
from app.clients.embedding_client import EmbeddingClient


class EmbeddingService:
    """向量化服务，为段落生成 Embedding"""

    def __init__(self, cleaning_service: CleaningService):
        self.cleaning_service = cleaning_service
        self.embedding_client = EmbeddingClient()

    async def generate_embeddings(self, document_id: str) -> Dict:
        """
        为单个文档生成 Embedding

        Args:
            document_id: 文档 ID

        Returns:
            更新后的 JSON 数据
        """
        # 加载缓存
        cache_data = self.cleaning_service.load_cache(document_id)
        if not cache_data:
            raise ValueError(f"缓存不存在: {document_id}")

        # 检查状态
        status = cache_data["metadata"]["status"]
        if status not in ["cleaned", "failed"]:
            raise ValueError(f"状态错误: {status}，期望 cleaned 或 failed")

        # 提取段落文本
        paragraphs = cache_data["paragraphs"]
        texts = [p["content"] for p in paragraphs]

        # 批量生成 Embedding
        try:
            embeddings = await self.embedding_client.embed(texts)
            
            # 将 Embedding 添加到段落
            for i, para in enumerate(paragraphs):
                para["embedding"] = embeddings[i]

            # 更新状态
            cache_data["metadata"]["status"] = "embedding"
            self.cleaning_service.save_cache(cache_data)

            return cache_data

        except Exception as e:
            # 标记失败
            cache_data["metadata"]["status"] = "failed"
            cache_data["metadata"]["error"] = f"Embedding 失败: {str(e)}"
            cache_data["metadata"]["retry_count"] += 1
            self.cleaning_service.save_cache(cache_data)
            raise

    async def batch_generate_embeddings(self, document_ids: List[str]) -> Dict:
        """
        批量生成 Embedding，错误隔离

        Args:
            document_ids: 文档 ID 列表

        Returns:
            {"success": [...], "failed": [...]}
        """
        results = {
            "success": [],
            "failed": [],
        }

        for doc_id in document_ids:
            try:
                await self.generate_embeddings(doc_id)
                results["success"].append(doc_id)
            except Exception as e:
                results["failed"].append({
                    "document_id": doc_id,
                    "error": str(e),
                })

        return results
