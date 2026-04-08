# 会话和消息相关的数据模型（Pydantic + SQLAlchemy）
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey
from sqlalchemy.orm import DeclarativeBase, relationship
import uuid


# ============ SQLAlchemy ORM 模型 ============

class Base(DeclarativeBase):
    pass


class SessionORM(Base):
    """会话表"""
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(200), nullable=False, default="新会话")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联消息
    messages = relationship("MessageORM", back_populates="session", cascade="all, delete-orphan")


class MessageORM(Base):
    """消息表"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)   # "user" | "assistant"
    content = Column(Text, nullable=False)
    sources = Column(Text, nullable=True)        # JSON 字符串，存引用来源
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    session = relationship("SessionORM", back_populates="messages")


class IngestTaskORM(Base):
    """导入任务表"""
    __tablename__ = "ingest_tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_path = Column(String(500), nullable=False)
    document_id = Column(String(200), nullable=True)
    status = Column(String(20), nullable=False, default="pending")  # pending|processing|completed|failed
    progress = Column(Integer, nullable=True)       # 0-100
    error = Column(Text, nullable=True)
    mineru_task_id = Column(String(200), nullable=True)  # MinerU 的任务 ID
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============ Pydantic Schema 模型 ============

class SessionCreate(BaseModel):
    title: str = "新会话"


class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


class SessionTitleUpdate(BaseModel):
    title: str


class MessageResponse(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    sources: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class HistoryResponse(BaseModel):
    session_id: str
    messages: list[MessageResponse]
