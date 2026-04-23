# 文档库模型
# 这个文件同时承载三类最小职责：
# 1. SQLAlchemy 持久化模型：真正落库的数据结构
# 2. Pydantic 领域模型：服务层和路由层传递的数据结构
# 3. 状态机规则：约束文档状态如何合法推进

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import Column, DateTime, String, Text

from app.models.session import Base

# 所有合法状态集中定义，避免字符串散落在代码各处。
DOCUMENT_STATUSES = (
    "pending",
    "parsing",
    "cleaning",
    "indexing",
    "completed",
    "failed",
    "deleting",
    "deleted",
)

# 索引模式定义：
# - brute: 暴力搜索（无索引）
# - distributed: 分布式多 Collection（每篇论文独立 Collection）
# - parent_child: 父子 Collection（已废弃，保留用于兼容性）
DOCUMENT_INDEX_MODES = (
    "brute",
    "distributed",
    "parent_child",  # 已废弃
)


def normalize_document_file_path(value: str) -> str:
    """规范化文档路径输入。

    这里不检查路径是否真实存在，
    因为 Task 3 只负责把最基础的输入边界收住。
    """
    normalized_value = value.strip()
    if not normalized_value:
        raise ValueError("file_path 不能为空")
    return normalized_value


def validate_document_index_mode(value: str) -> str:
    """校验索引模式是否合法。"""
    if value not in DOCUMENT_INDEX_MODES:
        raise ValueError(f"index_mode 必须是 {', '.join(DOCUMENT_INDEX_MODES)} 之一")
    return value

# 状态迁移表只描述“允许什么”，不描述具体业务实现。
# 这样状态机本身可以保持纯粹，服务层只负责决定何时触发迁移。
ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"parsing", "failed", "deleting"},
    "parsing": {"cleaning", "failed", "deleting"},
    "cleaning": {"indexing", "failed", "deleting"},
    "indexing": {"completed", "failed", "deleting"},
    "completed": {"indexing", "deleting"},
    "failed": {"pending", "deleting"},
    "deleting": {"deleted", "failed"},
    "deleted": set(),
}


class DocumentORM(Base):
    """文档库表。

    这里使用与现有 session 模块同一个 SQLAlchemy Base，
    这样 sqlite_repo 在建表时可以一次性创建所有模型。
    """

    __tablename__ = "documents"

    document_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False, default="")
    file_path = Column(String(500), nullable=False, default="")
    index_mode = Column(String(50), nullable=False, default="brute")
    status = Column(String(20), nullable=False, default="pending")
    tags = Column(Text, nullable=False, default="[]")
    error_stage = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class DocumentRecord(BaseModel):
    """服务层使用的文档记录。

    这个模型采用“返回新对象”的方式做状态迁移，
    这样可以符合不可变风格，避免对象被原地修改后产生隐藏副作用。
    """

    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    file_path: str = ""
    index_mode: str = "brute"
    status: str = "pending"
    tags: list[str] = Field(default_factory=list)
    error_stage: Optional[str] = None
    error_message: Optional[str] = None

    model_config = {"frozen": True}

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, value: str) -> str:
        """确保 file_path 至少是去空白后的非空字符串。

        Task 3 还不负责校验路径是否真实存在，
        这里只收住最基础的输入边界，避免空白路径落库。
        """
        return normalize_document_file_path(value)

    @field_validator("index_mode")
    @classmethod
    def validate_index_mode(cls, value: str) -> str:
        """确保索引模式始终处于当前任务支持的集合内。"""
        return validate_document_index_mode(value)

    @model_validator(mode="after")
    def validate_status(self) -> "DocumentRecord":
        """确保记录状态始终处于受控集合中。"""
        if self.status not in DOCUMENT_STATUSES:
            raise ValueError(f"不支持的文档状态: {self.status}")
        return self

    def transition(self, new_status: str) -> "DocumentRecord":
        """按状态机规则推进状态，并返回一个新记录。"""
        if new_status not in DOCUMENT_STATUSES:
            raise ValueError(f"不支持的目标状态: {new_status}")

        allowed_targets = ALLOWED_STATUS_TRANSITIONS.get(self.status, set())
        if new_status not in allowed_targets:
            raise ValueError(f"不允许从 {self.status} 迁移到 {new_status}")

        return self.model_copy(update={"status": new_status})

    @classmethod
    def from_orm_model(cls, orm_model: DocumentORM) -> "DocumentRecord":
        """把 ORM 对象转换为服务层记录。"""
        raw_tags = orm_model.tags or "[]"
        try:
            tags = json.loads(raw_tags)
        except json.JSONDecodeError:
            tags = []

        return cls(
            document_id=orm_model.document_id,
            title=orm_model.title,
            file_path=orm_model.file_path,
            index_mode=orm_model.index_mode,
            status=orm_model.status,
            tags=list(tags) if isinstance(tags, list) else [],
            error_stage=orm_model.error_stage,
            error_message=orm_model.error_message,
        )


class DocumentImportRequest(BaseModel):
    """导入文档请求。"""

    file_path: str
    title: str = ""
    index_mode: str = "brute"
    tags: list[str] = Field(default_factory=list)

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, value: str) -> str:
        """在 API 入参层先做一次最小边界校验。"""
        return normalize_document_file_path(value)

    @field_validator("index_mode")
    @classmethod
    def validate_index_mode(cls, value: str) -> str:
        """限制 API 允许的索引模式，避免非法值进入服务层。"""
        return validate_document_index_mode(value)


class DocumentReindexRequest(BaseModel):
    """重建索引请求。

    Task 3 只需要最小占位，不实现真正索引流程，
    因此这里只允许可选地覆盖 index_mode。
    """

    index_mode: Optional[str] = None
