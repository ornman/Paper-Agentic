"""助手 Schema"""

from __future__ import annotations

from pydantic import BaseModel, Field


class WrittenContextUpdate(BaseModel):
    session_id: str
    content: str = Field(default="", description="用户已写内容")


class EditorSelectionUpdate(BaseModel):
    session_id: str
    selection: str = Field(default="", description="用户圈选的文本")
    start: int | None = Field(default=None, description="选区在文档中的起始偏移")
    end: int | None = Field(default=None, description="选区在文档中的结束偏移")


class ContextState(BaseModel):
    session_id: str
    written_context: str = ""
    selection: str = ""


class PollingStartRequest(BaseModel):
    session_id: str
    interval: int = Field(default=5, ge=1, le=60, description="轮询间隔（秒）")
