# 导入模块 DTO
# 这里定义 Task 4 需要的最小数据契约：
# 1. 清洗后的块结构（支持文本和图片）
# 2. 清洗后的文档结构
# 3. MinerU 提交/轮询过程中会用到的最小任务状态结构

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class CleanedBlock(BaseModel):
    """清洗后保留下来的块（支持文本和图片）.

    这里保留完整的块结构，包括：
    1. 文本块：block_type="text", content="正文内容"
    2. 图片块：block_type="image", image_path="xxx.jpg", content="VLM描述"
    3. 其他块：block_type="title" 等
    """

    block_id: str
    page: int
    block_type: str  # "text", "image", "title" 等
    content: str  # 文本内容或图片描述
    bbox: list[int] | None = None  # 边界框 [x1, y1, x2, y2]
    image_path: str | None = None  # 图片路径（相对于 images/ 目录）
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class CleanedDocument(BaseModel):
    """清洗后的文档结果（保留完整结构）."""

    document_id: str
    title: str
    file_path: str
    index_mode: str
    blocks: list[CleanedBlock] = Field(default_factory=list)
    raw_block_count: int = 0
    cleaned_block_count: int = 0
    removed_block_count: int = 0

    model_config = {"frozen": True}


class MineruTaskSubmission(BaseModel):
    """MinerU 提交任务后的最小返回。"""

    task_id: str

    model_config = {"frozen": True}


class MineruTaskState(BaseModel):
    """MinerU 轮询状态的最小统一视图。"""

    status: str
    result_url: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    message: Optional[str] = None

    model_config = {"frozen": True}
