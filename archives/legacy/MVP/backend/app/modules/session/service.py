# 会话服务（新架构）
# 管理会话历史记录的查询和清理

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# 直接使用 sqlite_repo 的函数式 API
from app.repositories import sqlite_repo as repo


class SessionService:
    """会话服务."""

    def __init__(self) -> None:
        # 不需要 repository 参数，直接使用函数式 API
        pass

    def get_history(self, session_id: str) -> list[dict]:
        """获取会话历史.

        Args:
            session_id: 会话 ID

        Returns:
            消息列表
        """
        messages = repo.get_messages(session_id)
        return [
            {
                "id": m.id,
                "session_id": m.session_id,
                "role": m.role,
                "content": m.content,
                "sources": json.loads(m.sources) if m.sources else None,
                "created_at": m.created_at,
            }
            for m in messages
        ]

    def clear_history(self, session_id: str) -> int:
        """清空会话历史，返回删除数量.

        Args:
            session_id: 会话 ID

        Returns:
            删除的消息数量
        """
        return repo.clear_messages(session_id)
