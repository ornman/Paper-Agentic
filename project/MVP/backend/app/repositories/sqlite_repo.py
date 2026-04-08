# SQLite 仓储层
# 使用 SQLAlchemy ORM 管理会话、消息、导入任务和文档库记录
from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session as DBSession
from app.models.session import Base, SessionORM, MessageORM, IngestTaskORM
from app.core.config import get_settings
import json


def _get_engine():
    """创建 SQLAlchemy 引擎（SQLite）"""
    settings = get_settings()
    db_path = settings.sqlite_db_path
    # 确保目录存在
    from pathlib import Path
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", echo=False)


# 模块级引擎（单例）
_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = _get_engine()
        # 自动建表
        Base.metadata.create_all(_engine)
    return _engine


def ensure_all_tables_created():
    """确保当前已注册到 Base 的所有 ORM 模型都完成建表。

    为什么需要这个函数：
    现有 get_engine() 只在引擎第一次创建时自动建表。
    如果后续才导入新的 ORM 模型，旧引擎不会重新执行 create_all，
    新表就不会出现。Task 3 新增 documents 表，正好会踩到这个问题。
    """
    Base.metadata.create_all(get_engine())


# ============ 会话操作 ============

def create_session(title: str = "新会话") -> SessionORM:
    """创建新会话"""
    with DBSession(get_engine()) as db:
        session = SessionORM(title=title)
        db.add(session)
        db.commit()
        db.refresh(session)
        # 返回脱离 session 的对象
        db.expunge(session)
        return session


def get_session(session_id: str) -> Optional[SessionORM]:
    """按 ID 获取会话"""
    with DBSession(get_engine()) as db:
        session = db.get(SessionORM, session_id)
        if session:
            db.expunge(session)
        return session


def list_sessions(page: int = 1, page_size: int = 20) -> tuple[list[SessionORM], int]:
    """分页获取会话列表，返回 (items, total)"""
    with DBSession(get_engine()) as db:
        total = db.scalar(select(func.count()).select_from(SessionORM))
        offset = (page - 1) * page_size
        sessions = db.scalars(
            select(SessionORM)
            .order_by(SessionORM.updated_at.desc())
            .offset(offset)
            .limit(page_size)
        ).all()
        for s in sessions:
            db.expunge(s)
        return list(sessions), total


def update_session_title(session_id: str, title: str) -> Optional[SessionORM]:
    """更新会话标题"""
    with DBSession(get_engine()) as db:
        session = db.get(SessionORM, session_id)
        if not session:
            return None
        session.title = title
        session.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(session)
        db.expunge(session)
        return session


def delete_session(session_id: str) -> bool:
    """删除会话（级联删除消息）"""
    with DBSession(get_engine()) as db:
        session = db.get(SessionORM, session_id)
        if not session:
            return False
        db.delete(session)
        db.commit()
        return True


# ============ 消息操作 ============

def add_message(
    session_id: str,
    role: str,
    content: str,
    sources: Optional[list] = None
) -> MessageORM:
    """新增消息，同时更新会话的 updated_at"""
    with DBSession(get_engine()) as db:
        msg = MessageORM(
            session_id=session_id,
            role=role,
            content=content,
            sources=json.dumps(sources, ensure_ascii=False) if sources else None,
        )
        db.add(msg)
        # 更新会话时间
        session = db.get(SessionORM, session_id)
        if session:
            session.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(msg)
        db.expunge(msg)
        return msg


def get_messages(session_id: str) -> list[MessageORM]:
    """获取会话所有消息（按时间正序）"""
    with DBSession(get_engine()) as db:
        messages = db.scalars(
            select(MessageORM)
            .where(MessageORM.session_id == session_id)
            .order_by(MessageORM.created_at.asc())
        ).all()
        for m in messages:
            db.expunge(m)
        return list(messages)


def get_message_count(session_id: str) -> int:
    """获取会话消息数量"""
    with DBSession(get_engine()) as db:
        return db.scalar(
            select(func.count())
            .select_from(MessageORM)
            .where(MessageORM.session_id == session_id)
        ) or 0


def clear_messages(session_id: str) -> int:
    """清空会话历史，返回删除数量"""
    with DBSession(get_engine()) as db:
        messages = db.scalars(
            select(MessageORM).where(MessageORM.session_id == session_id)
        ).all()
        count = len(messages)
        for m in messages:
            db.delete(m)
        db.commit()
        return count


# ============ 导入任务操作 ============

def create_ingest_task(file_path: str, document_id: Optional[str] = None) -> IngestTaskORM:
    """创建导入任务"""
    with DBSession(get_engine()) as db:
        task = IngestTaskORM(file_path=file_path, document_id=document_id)
        db.add(task)
        db.commit()
        db.refresh(task)
        db.expunge(task)
        return task


def get_ingest_task(task_id: str) -> Optional[IngestTaskORM]:
    """按 ID 获取导入任务"""
    with DBSession(get_engine()) as db:
        task = db.get(IngestTaskORM, task_id)
        if task:
            db.expunge(task)
        return task


def update_ingest_task(
    task_id: str,
    status: Optional[str] = None,
    progress: Optional[int] = None,
    error: Optional[str] = None,
    mineru_task_id: Optional[str] = None,
) -> Optional[IngestTaskORM]:
    """更新导入任务状态"""
    with DBSession(get_engine()) as db:
        task = db.get(IngestTaskORM, task_id)
        if not task:
            return None
        if status is not None:
            task.status = status
        if progress is not None:
            task.progress = progress
        if error is not None:
            task.error = error
        if mineru_task_id is not None:
            task.mineru_task_id = mineru_task_id
        task.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(task)
        db.expunge(task)
        return task


def list_ingest_tasks(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None
) -> tuple[list[IngestTaskORM], int]:
    """分页获取导入任务列表"""
    with DBSession(get_engine()) as db:
        query = select(IngestTaskORM)
        count_query = select(func.count()).select_from(IngestTaskORM)
        if status:
            query = query.where(IngestTaskORM.status == status)
            count_query = count_query.where(IngestTaskORM.status == status)
        total = db.scalar(count_query) or 0
        offset = (page - 1) * page_size
        tasks = db.scalars(
            query.order_by(IngestTaskORM.created_at.desc())
            .offset(offset)
            .limit(page_size)
        ).all()
        for t in tasks:
            db.expunge(t)
        return list(tasks), total
