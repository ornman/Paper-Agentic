# 导入服务编排
# 当前只做 Task 4 最小闭环：
# 1. pending -> parsing
# 2. 调 MinerU 拉结构化结果
# 3. parsing -> cleaning
# 4. 调 cleaning 过滤正文块
# 5. cleaning -> indexing -> completed（这里只是状态占位，不做 Task 5 索引细节）
# 6. 任一阶段失败都映射到 failed，并写入 error_stage / error_message

from __future__ import annotations

from typing import Optional

from app.core.errors import IngestionError
from app.modules.ingestion.cleaning import clean_mineru_payload
from app.modules.ingestion.dto import CleanedDocument
from app.modules.ingestion.mineru_client import MineruClient
from app.modules.library.models import DocumentRecord
from app.modules.library.repository import LibraryRepository

# Task 4 当前能接受的 MinerU 最小成功载荷结构。
# 如果 success payload 连这个最小结构都不满足，就说明是响应契约漂移，
# 不能再被误归因为“清洗后无正文”。
_MINERU_MINIMAL_SUCCESS_KEYS = {"pages"}


class IngestionService:
    """最小导入编排服务。"""

    def __init__(
        self,
        *,
        repository: Optional[LibraryRepository] = None,
        mineru_client: Optional[MineruClient] = None,
    ) -> None:
        self.repository = repository or LibraryRepository()
        self.mineru_client = mineru_client or MineruClient()

    def ingest_document(self, record: DocumentRecord) -> DocumentRecord:
        """执行文档导入链路，并返回最终文档状态。"""
        current_record = self.repository.save_document(record.transition("parsing"))

        try:
            mineru_payload = self.mineru_client.run_pdf_task(current_record.file_path)
            self._validate_success_payload_shape(mineru_payload)

            current_record = self.repository.save_document(current_record.transition("cleaning"))
            cleaned_document = self._clean_document(current_record, mineru_payload)

            # 这里必须把“无有效正文”视为失败，而不是继续伪造 completed。
            # 本质上，清洗后 0 块代表没有可索引正文，继续推进只会制造假成功。
            if cleaned_document.cleaned_block_count == 0:
                raise IngestionError(
                    code="cleaned_document_empty",
                    message="清洗后无有效正文块，导入失败",
                    detail={"document_id": current_record.document_id},
                )

            # Task 4 不实现真正索引，只把状态机推进到可验证的完成态。
            current_record = self.repository.save_document(current_record.transition("indexing"))
            completed_record = current_record.transition("completed").model_copy(
                update={
                    "error_stage": None,
                    "error_message": None,
                }
            )
            return self.repository.save_document(completed_record)
        except IngestionError as exc:
            return self._mark_failed(current_record, exc)
        except Exception as exc:  # noqa: BLE001
            unexpected_error = IngestionError(
                code="ingestion_failed",
                message=f"导入链路执行失败: {exc}",
                detail={"document_id": current_record.document_id},
            )
            return self._mark_failed(current_record, unexpected_error)

    def _clean_document(self, record: DocumentRecord, mineru_payload: dict) -> CleanedDocument:
        """调用清洗入口，把 MinerU 结果归一化为正文块。"""
        return clean_mineru_payload(
            document_id=record.document_id,
            title=record.title,
            file_path=record.file_path,
            index_mode=record.index_mode,
            payload=mineru_payload,
        )

    def _validate_success_payload_shape(self, mineru_payload: dict) -> None:
        """校验成功态 payload 的最小结构。

        这里仍然只守住 Task 4 真正需要的最小契约，但要比“只看顶层有 pages 键”更严格：
        1. payload 必须是对象。
        2. pages 必须是数组。
        3. pages 中的每一项都必须是对象。

        原因很直接：
        - 这些约束一旦不满足，就不是“清洗后没有正文”，而是上游成功态响应已经漂移。
        - 如果继续把坏结构送进 cleaning，错误语义就会被污染成 cleaned_document_empty。
        """
        if not isinstance(mineru_payload, dict):
            raise IngestionError(
                code="mineru_invalid_response",
                message="MinerU 成功结果不是 JSON 对象",
                detail={"payload_type": type(mineru_payload).__name__},
            )
        if not _MINERU_MINIMAL_SUCCESS_KEYS.issubset(mineru_payload.keys()):
            raise IngestionError(
                code="mineru_invalid_response",
                message="MinerU 成功结果缺少最小正文结构字段",
                detail={"required_keys": sorted(_MINERU_MINIMAL_SUCCESS_KEYS)},
            )

        pages = mineru_payload.get("pages")
        if not isinstance(pages, list):
            raise IngestionError(
                code="mineru_invalid_response",
                message="pages 必须是数组",
                detail={"pages_type": type(pages).__name__},
            )

        for page_index, page_item in enumerate(pages):
            if not isinstance(page_item, dict):
                raise IngestionError(
                    code="mineru_invalid_response",
                    message=f"pages[{page_index}] 必须是对象",
                    detail={"page_item_type": type(page_item).__name__},
                )

    def _mark_failed(self, record: DocumentRecord, error: IngestionError) -> DocumentRecord:
        """把当前记录推进到 failed，并写入统一错误信息。"""
        failed_record = record.transition("failed").model_copy(
            update={
                "error_stage": error.stage,
                "error_message": error.message,
            }
        )
        return self.repository.save_document(failed_record)
