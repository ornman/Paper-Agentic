# 索引服务
# 阶段3：读取 JSON → ChromaDB + BM25
from typing import List, Dict
from app.services.cleaning_service import CleaningService
from app.repositories.chroma_repo import ChromaRepo
from app.repositories.bm25_repo import BM25Repo


class IndexingService:
    """索引服务，将向量写入 ChromaDB 和 BM25"""

    def __init__(self, cleaning_service: CleaningService):
        self.cleaning_service = cleaning_service
        self.chroma_repo = ChromaRepo()
        self.bm25_repo = BM25Repo()

    def index_document(self, document_id: str) -> Dict:
        """
        将单个文档索引到 ChromaDB 和 BM25

        Args:
            document_id: 文档 ID

        Returns:
            {"vector_count": int, "bm25_count": int}
        """
        # 加载缓存
        cache_data = self.cleaning_service.load_cache(document_id)
        if not cache_data:
            raise ValueError(f"缓存不存在: {document_id}")

        # 检查状态
        status = cache_data["metadata"]["status"]
        if status not in ["embedding", "indexed"]:
            raise ValueError(f"状态错误: {status}，期望 embedding 或 indexed")

        # 如果已索引，跳过（幂等性）
        if status == "indexed":
            return {
                "document_id": document_id,
                "vector_count": 0,
                "bm25_count": 0,
                "message": "已索引，跳过",
            }

        try:
            paragraphs = cache_data["paragraphs"]
            
            # 提取向量和元数据
            ids = []
            embeddings = []
            documents = []
            metadatas = []

            for para in paragraphs:
                if "embedding" not in para:
                    raise ValueError(f"段落缺少 embedding: {para['id']}")

                ids.append(para["id"])
                embeddings.append(para["embedding"])
                documents.append(para["content"])
                metadatas.append({
                    "document_id": document_id,
                    "document": cache_data["source_name"],
                    "page": para.get("page"),
                    "type": para.get("type", "paragraph"),
                })

            # 写入 ChromaDB
            self.chroma_repo.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )

            # 写入 BM25
            self.bm25_repo.add_batch(ids, documents)
            self.bm25_repo.save()

            # 更新状态
            cache_data["metadata"]["status"] = "indexed"
            self.cleaning_service.save_cache(cache_data)

            return {
                "document_id": document_id,
                "vector_count": len(ids),
                "bm25_count": len(ids),
            }

        except Exception as e:
            # 标记失败
            cache_data["metadata"]["status"] = "failed"
            cache_data["metadata"]["error"] = f"索引失败: {str(e)}"
            cache_data["metadata"]["retry_count"] += 1
            self.cleaning_service.save_cache(cache_data)
            raise

    def batch_index_documents(self, document_ids: List[str]) -> Dict:
        """
        批量索引，错误隔离

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
                result = self.index_document(doc_id)
                results["success"].append(result)
            except Exception as e:
                results["failed"].append({
                    "document_id": doc_id,
                    "error": str(e),
                })

        return results

    def delete_document(self, document_id: str):
        """删除文档的所有索引"""
        # 从 ChromaDB 删除
        self.chroma_repo.delete_by_document(document_id)
        
        # 从 BM25 删除（需要读取缓存获取段落 ID）
        cache_data = self.cleaning_service.load_cache(document_id)
        if cache_data:
            for para in cache_data["paragraphs"]:
                self.bm25_repo.delete_by_id(para["id"])
        
        # 删除缓存
        cache_file = self.cleaning_service.cache_dir / f"{document_id}.json"
        if cache_file.exists():
            cache_file.unlink()
