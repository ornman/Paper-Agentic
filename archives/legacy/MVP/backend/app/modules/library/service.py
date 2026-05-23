# 文档库服务层
# 这一层负责最小业务编排：创建记录、状态迁移、删除和重建索引占位。

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional
from urllib.parse import urlsplit

from app.modules.library.models import (
    DocumentRecord,
    normalize_document_file_path,
    validate_document_index_mode,
)
from app.modules.library.repository import LibraryRepository

if TYPE_CHECKING:
    from app.modules.ingestion.service import IngestionService


class LibraryService:
    """文档库服务。"""

    def __init__(
        self,
        repository: Optional[LibraryRepository] = None,
        ingestion_service: Optional["IngestionService"] = None,
    ) -> None:
        self.repository = repository or LibraryRepository()
        self._ingestion_service = ingestion_service

    def import_document(
        self,
        file_path: str,
        title: str = "",
        index_mode: str = "brute",
        tags: Optional[list[str]] = None,
    ) -> DocumentRecord:
        """创建一条待处理文档记录。

        Task 3 只要求建立文档库记录和状态机，
        不接 MinerU，也不做真正索引。
        所以这里的最小实现就是把文档登记为 pending。

        这里显式做一次服务层边界校验，原因是：
        1. 路由层不是唯一入口，测试和未来任务可能直接调用服务层。
        2. 仓储层只负责落库，不应该承担业务输入校验职责。
        """
        normalized_file_path = normalize_document_file_path(file_path)
        normalized_index_mode = validate_document_index_mode(index_mode)
        normalized_title = title.strip() or Path(normalized_file_path).stem
        record = DocumentRecord(
            title=normalized_title,
            file_path=normalized_file_path,
            index_mode=normalized_index_mode,
            status="pending",
            tags=list(tags or []),
            error_stage=None,
            error_message=None,
        )
        return self.repository.save_document(record)

    async def import_pdf(
        self,
        file_path: str,
        index_mode: str = “distributed”,
        title: str = “”,
        tags: Optional[list[str]] = None,
    ) -> DocumentRecord:
        “””登记 PDF 并立即触发导入链路。

        为什么不直接复用 import_document 作为公开入口名：
        - Task 3 的 import_document 语义是”只登记”。
        - Task 4 新增的是”登记后继续导入”。
        - 拆成 import_pdf 可以避免把原有行为悄悄改坏，测试边界也更清晰。

        这里额外收紧 PDF 导入边界，但不回写到 import_document。
        原因是 Task 3 的最小登记语义必须保持不变；
        Task 4 只需要把真正进入 MinerU 链路的输入面收住即可。

        注意：此函数现在是异步的，以避免在 FastAPI 事件循环中使用 asyncio.run()。
        “””
        normalized_pdf_path = self._validate_import_pdf_path(file_path)
        created_record = self.import_document(
            file_path=normalized_pdf_path,
            title=title,
            index_mode=index_mode,
            tags=tags,
        )
        return await self._get_ingestion_service().ingest_document(created_record)

    async def resume_import(
        self,
        document_id: str,
    ) -> DocumentRecord:
        """恢复失败的导入任务（断点续传）.

        Args:
            document_id: 文档 ID

        Returns:
            更新后的文档记录

        Raises:
            KeyError: 文档不存在
            ValueError: 文档状态不允许恢复
        """
        record = self.get_document(document_id)

        # 只允许从 failed 状态恢复
        if record.status != "failed":
            raise ValueError(
                f"只能从 failed 状态恢复，当前状态: {record.status}"
            )

        # 重置到 pending 状态
        pending_record = record.transition("pending")
        updated_record = self.repository.save_document(
            pending_record.model_copy(
                update={
                    "error_stage": None,
                    "error_message": None,
                }
            )
        )

        # 重新触发导入
        return await self._get_ingestion_service().ingest_document(updated_record)

    def _get_ingestion_service(self) -> "IngestionService":
        """按需构造 ingestion service，避免模块导入阶段形成循环依赖。"""
        if self._ingestion_service is None:
            from app.modules.ingestion.service import IngestionService

            self._ingestion_service = IngestionService(repository=self.repository)
        return self._ingestion_service

    def _validate_import_pdf_path(self, file_path: str) -> str:
        """校验真正进入 PDF 导入链路的文件路径。

        这里故意只挂在 import_pdf 上，而不是复用到 import_document，
        因为两者语义不同：
        - import_document: 最小登记
        - import_pdf: 进入 MinerU 导入链路

        安全边界目标：
        1. 只接受本地路径，不接受 URL / file URI / UNC 网络路径。
        2. 只接受 .pdf。
        3. 路径必须存在且是普通文件。
        """
        import os

        normalized_file_path = file_path.strip()
        if not normalized_file_path:
            raise ValueError("import_pdf 只接受本地 PDF 文件路径")

        # 🔴 P2-1 优化：路径遍历检测（检测 .. 和 . 开头）
        if ".." in normalized_file_path or normalized_file_path.startswith("."):
            raise ValueError("检测到路径遍历攻击，路径不能包含 .. 或以 . 开头")

        parsed_path = urlsplit(normalized_file_path)
        has_uri_scheme = "://" in normalized_file_path
        if has_uri_scheme and (parsed_path.scheme or parsed_path.netloc):
            raise ValueError("import_pdf 只接受本地 PDF 文件路径")
        if normalized_file_path.startswith(("//", "\\\\")):
            raise ValueError("import_pdf 只接受本地 PDF 文件路径")

        # 使用 os.path 而非 Path 进行文件存在性检查
        # 原因：Windows 文件系统对中文引号等特殊字符的处理更稳定
        if not normalized_file_path.lower().endswith(".pdf"):
            raise ValueError("import_pdf 只接受 .pdf 文件")

        # 🔴 P2-1 优化：规范化路径并检测符号链接
        local_path = Path(normalized_file_path).resolve()

        # 🔴 P2-1 优化：检测符号链接
        if local_path.is_symlink():
            raise ValueError("不允许使用符号链接，以防止路径遍历攻击")

        if not local_path.is_file():
            raise ValueError(f"PDF 文件不存在: {local_path}")

        return str(local_path)

    def list_documents(self) -> list[DocumentRecord]:
        """返回当前可见文档列表。"""
        return self.repository.list_documents()

    def get_document(self, document_id: str) -> DocumentRecord:
        """读取单个文档，不存在时抛出明确错误。"""
        record = self.repository.get_document(document_id)
        if record is None:
            raise KeyError(f"文档不存在: {document_id}")
        return record

    def transition_document(self, document_id: str, new_status: str) -> DocumentRecord:
        """把指定文档推进到下一个状态。"""
        record = self.get_document(document_id)
        updated_record = record.transition(new_status)
        return self.repository.save_document(updated_record)

    def delete_document(self, document_id: str) -> DocumentRecord:
        """软删除文档。

        为了保留删除状态，这里不物理删行，而是按状态机推进到 deleted。
        """
        record = self.get_document(document_id)
        deleting_record = record.transition("deleting")
        deleted_record = deleting_record.transition("deleted")
        return self.repository.save_document(deleted_record)

    def reindex_document(self, document_id: str, index_mode: Optional[str] = None) -> DocumentRecord:
        """重建索引占位实现。

        Task 3 还没有真正的索引模块，
        因此这里必须避免把健康的 completed 文档推进到 indexing，
        否则会制造一个当前任务无法自愈的卡死状态。

        当前占位策略：
        1. completed -> 直接拒绝，要求后续真实索引流程落地后再开放。
        2. failed -> 允许回到 pending，表达“可重新进入处理链路”。
        3. deleted -> 明确拒绝。
        4. 其他状态 -> 保持原状态，只允许更新合法的 index_mode 与清空错误信息。
        """
        record = self.get_document(document_id)
        normalized_index_mode = validate_document_index_mode(index_mode) if index_mode is not None else record.index_mode
        prepared_record = record.model_copy(
            update={
                "index_mode": normalized_index_mode,
                "error_stage": None,
                "error_message": None,
            }
        )

        if prepared_record.status == "completed":
            raise ValueError("completed 文档在 Task 3 占位实现中暂不支持重建索引")
        if prepared_record.status == "failed":
            prepared_record = prepared_record.transition("pending")
        elif prepared_record.status == "deleted":
            raise ValueError("已删除文档不能重建索引")

        return self.repository.save_document(prepared_record)
