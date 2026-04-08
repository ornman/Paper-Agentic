# 文档库仓储层
# 这一层只负责和 SQLite 打交道，不掺杂业务编排。

from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.modules.library.models import DocumentORM, DocumentRecord
from app.repositories import sqlite_repo


class LibraryRepository:
    """文档库 SQLite 仓储。"""

    def __init__(self) -> None:
        # 即使引擎已经初始化过，也再次显式建表，
        # 这样可以覆盖“先启动旧模块、后导入新 ORM 模型”的场景。
        sqlite_repo.ensure_all_tables_created()

    def save_document(self, record: DocumentRecord) -> DocumentRecord:
        """新增或更新文档记录。"""
        with DBSession(sqlite_repo.get_engine()) as db:
            orm_record = db.get(DocumentORM, record.document_id)

            if orm_record is None:
                orm_record = DocumentORM(document_id=record.document_id)
                db.add(orm_record)

            orm_record.title = record.title
            orm_record.file_path = record.file_path
            orm_record.index_mode = record.index_mode
            orm_record.status = record.status
            orm_record.tags = json.dumps(record.tags, ensure_ascii=False)
            orm_record.error_stage = record.error_stage
            orm_record.error_message = record.error_message

            db.commit()
            db.refresh(orm_record)
            db.expunge(orm_record)
            return DocumentRecord.from_orm_model(orm_record)

    def get_document(self, document_id: str) -> Optional[DocumentRecord]:
        """按 ID 读取单条文档记录。"""
        with DBSession(sqlite_repo.get_engine()) as db:
            orm_record = db.get(DocumentORM, document_id)
            if orm_record is None:
                return None
            db.expunge(orm_record)
            return DocumentRecord.from_orm_model(orm_record)

    def list_documents(self, include_deleted: bool = False) -> list[DocumentRecord]:
        """列出文档记录。

        默认过滤 deleted，避免前端默认列表混入已经删掉的文档。
        """
        with DBSession(sqlite_repo.get_engine()) as db:
            stmt = select(DocumentORM).order_by(DocumentORM.created_at.desc())
            if not include_deleted:
                stmt = stmt.where(DocumentORM.status != "deleted")

            orm_records = db.scalars(stmt).all()
            for orm_record in orm_records:
                db.expunge(orm_record)

            return [DocumentRecord.from_orm_model(orm_record) for orm_record in orm_records]
