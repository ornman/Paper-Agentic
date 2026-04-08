# 查询相关的请求/响应模型
from typing import Optional
from pydantic import BaseModel


class QueryContext(BaseModel):
    """4 种输入场景的上下文，权重由后端根据场景自动判断"""
    written_content: Optional[str] = None   # 已写内容
    selected_text: Optional[str] = None     # 圈选文本
    prompt: Optional[str] = None            # 提示词


class AskRequest(BaseModel):
    """问答请求"""
    session_id: str
    query: str
    context: Optional[QueryContext] = None


class SourceItem(BaseModel):
    """单个引用项"""
    id: int                     # 引用编号 [1], [2]...
    content: str                # 引用内容片段
    document: str               # 来源文档
    page: Optional[int] = None  # 页码
    score: float = 0.0          # 相关性分数


class StreamChunk(BaseModel):
    """SSE 文本块事件"""
    content: str
    index: int


class StreamSources(BaseModel):
    """SSE 引用来源事件"""
    sources: list[SourceItem]


class StreamDone(BaseModel):
    """SSE 完成事件"""
    total_tokens: int = 0


class StreamError(BaseModel):
    """SSE 错误事件"""
    code: int
    message: str


class RetrieveRequest(BaseModel):
    """纯检索请求"""
    query: str
    top_k: int = 10


class RetrieveResult(BaseModel):
    """单个检索结果"""
    id: str
    content: str
    document: str
    page: Optional[int] = None
    score: float
    layer: str  # "section" | "paragraph" | "sentence"


class RetrieveResponse(BaseModel):
    """纯检索响应"""
    query: str
    rewritten_query: str
    results: list[RetrieveResult]
