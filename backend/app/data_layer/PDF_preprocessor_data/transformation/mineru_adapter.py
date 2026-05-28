"""MinerU 适配器

MinerU 精准解析 API 的 pipeline 接口。
PDF/DOCX/DOC/PPTX/XLSX 等多格式统一解析，失败即失败，不降级。

MinerU 输出：Markdown + JSON（layout/content_list）+ images/
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("paper-assistant")

# MinerU 支持的文件类型
_MINERU_SUPPORTED_SUFFIXES = {".pdf", ".docx", ".doc", ".pptx", ".xlsx", ".ppt", ".xls"}


@dataclass(frozen=True)
class MinerUConversionResult:
    """MinerU 转换结果"""
    markdown: str
    page_count: int
    char_count: int
    success: bool
    error: str | None = None
    elapsed_s: float = 0.0
    metadata: dict = field(default_factory=dict)  # JSON 元数据
    logs: list[dict] | None = None


async def convert_with_mineru(
    file_path: Path,
    *,
    page_ranges: str | None = None,
    model_version: str = "pipeline",
    language: str = "ch",
    on_progress=None,
) -> MinerUConversionResult:
    """用 MinerU 精准解析 API 将文档转为 Markdown

    支持 MinerU 原生支持的所有格式：PDF/DOCX/DOC/PPTX/XLSX/PPT/XLS。

    Args:
        file_path: 文件路径
        page_ranges: 页码范围，如 "1-20"（仅 PDF 有效）
        model_version: 模型版本 (pipeline / vlm / MinerU-HTML)
        language: 文档语言
        on_progress: 进度回调 (MinerUProgress) -> None

    Returns:
        MinerUConversionResult
    """
    if not file_path.exists():
        return MinerUConversionResult(
            markdown="",
            page_count=0,
            char_count=0,
            success=False,
            error=f"文件不存在: {file_path}",
        )

    if file_path.suffix.lower() not in _MINERU_SUPPORTED_SUFFIXES:
        return MinerUConversionResult(
            markdown="",
            page_count=0,
            char_count=0,
            success=False,
            error=f"不支持的文件格式: {file_path.suffix}，支持: {', '.join(sorted(_MINERU_SUPPORTED_SUFFIXES))}",
        )

    token = os.environ.get("MINERU_TOKEN", "")
    if not token:
        return MinerUConversionResult(
            markdown="",
            page_count=0,
            char_count=0,
            success=False,
            error="MINERU_TOKEN 环境变量未配置",
        )

    from .mineru_client import MinerUClient

    client = MinerUClient(
        token=token,
        on_progress=on_progress,
    )

    result = await client.parse_document(
        file_path,
        page_ranges=page_ranges,
        model_version=model_version,
        language=language,
    )

    return MinerUConversionResult(
        markdown=result.markdown,
        page_count=result.page_count,
        char_count=result.char_count,
        success=result.success,
        error=result.error,
        elapsed_s=result.elapsed_s,
        metadata=result.metadata,
        logs=result.logs,
    )
