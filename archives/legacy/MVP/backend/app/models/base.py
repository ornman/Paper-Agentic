# 统一 API 响应模型和基础数据结构
from typing import Generic, TypeVar, Optional
from pydantic import BaseModel
from dataclasses import dataclass, field

T = TypeVar("T")


@dataclass
class Chunk:
    """文本块数据结构."""
    id: str
    paper: str
    chunk_type: str  # "text" or "image"
    content: str
    section: str = ""
    page: int = 0
    image_path: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应格式"""
    code: int = 0
    data: Optional[T] = None
    message: str = "success"


class PaginatedData(BaseModel, Generic[T]):
    """分页数据"""
    items: list[T]
    total: int
    page: int
    page_size: int


class ErrorCode:
    """业务错误码"""
    SUCCESS = 0

    # LLM 相关 (1000-1999)
    LLM_API_KEY_INVALID = 1001
    LLM_MODEL_UNAVAILABLE = 1002
    LLM_RATE_LIMIT = 1003
    LLM_TIMEOUT = 1004

    # 检索相关 (2000-2999)
    VECTOR_DB_ERROR = 2001
    NO_RELEVANT_RESULTS = 2002
    RERANK_ERROR = 2003

    # 导入相关 (3000-3999)
    FILE_FORMAT_UNSUPPORTED = 3001
    PARSE_FAILED = 3002
    TASK_NOT_FOUND = 3003

    # 会话相关 (4000-4999)
    SESSION_NOT_FOUND = 4001
    HISTORY_EMPTY = 4002

    # 系统错误 (9000-9999)
    INTERNAL_ERROR = 9001
    SERVICE_UNAVAILABLE = 9002
