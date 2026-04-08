# 导入模块 DTO
# 这里定义 Task 4 需要的最小数据契约：
# 1. 清洗后的块结构
# 2. 清洗后的文档结构
# 3. MinerU 提交/轮询过程中会用到的最小任务状态结构

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class CleanedBlock(BaseModel):
    """清洗后保留下来的正文块。

    这里显式保留 block_id/page/text，原因是：
    1. 后续索引阶段一定需要稳定块 ID。
    2. page 是来源引用的最小定位信息。
    3. text 是当前 Task 4 真正有业务价值的正文内容。
    """

    block_id: str
    page: int
    text: str

    model_config = {"frozen": True}


class CleanedDocument(BaseModel):
    """清洗后的文档结果。"""

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
