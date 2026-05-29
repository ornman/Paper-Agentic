"""文档转换器

MinerU 精准解析 API 唯一主链路。MinerU 失败即为转换失败。

输出：markdown + metadata + 图片路径列表 + 处理日志
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("paper-assistant")


@dataclass(frozen=True)
class ConversionResult:
    """PDF 转换结果"""
    markdown: str
    metadata: dict
    images: list[dict]  # [{"page": int, "path": str}]
    success: bool = True
    error: str | None = None
    logs: list[dict] = field(default_factory=list)
    mineru_metadata: dict = field(default_factory=dict)  # MinerU JSON 元数据（layout/content_list/image_paths）


async def convert_pdf(
    file_path: Path,
    output_dir: Path | None = None,
    on_mineru_progress=None,
) -> ConversionResult:
    """PDF 转换入口

    MinerU 精准解析 API 唯一主链路。失败即失败。

    Args:
        file_path: 文件路径（仅 PDF）
        output_dir: 图片输出目录
        on_mineru_progress: MinerU 进度回调
    """
    if not file_path.exists():
        return ConversionResult(
            markdown="", metadata={}, images=[],
            success=False, error=f"文件不存在: {file_path}",
            logs=[_log("error", "文件不存在", file_path=str(file_path))],
        )

    logs: list[dict] = []
    t0 = time.perf_counter()

    # 1. 获取配置
    from app.service_layer.config.settings import get_settings
    settings = get_settings()

    token = settings.mineru_api_key
    if not token:
        # 向后兼容：读 MINERU_TOKEN
        token = os.environ.get("MINERU_TOKEN", "")
        if token:
            logger.warning("MINERU_TOKEN 已废弃，请使用 MINERU_API_KEY")

    if not token:
        return ConversionResult(
            markdown="", metadata={}, images=[],
            success=False, error="MinerU API Key 未配置",
            logs=[_log("error", "MinerU API Key 未配置")],
        )

    # 2. MinerU 解析
    logs.append(_log("info", "MinerU 解析"))
    from .mineru_client import MinerUClient

    client = MinerUClient(
        token=token,
        base_url=settings.mineru_base_url or "https://mineru.net/api/v4",
        timeout_s=settings.mineru_timeout,
        poll_interval_s=settings.mineru_poll_interval,
        on_progress=on_mineru_progress,
    )
    mineru_result = await client.parse_document(file_path)

    if not mineru_result.success:
        logs.append(_log("error", f"MinerU 解析失败: {mineru_result.error}"))
        return ConversionResult(
            markdown="", metadata={}, images=[],
            success=False, error=mineru_result.error, logs=logs,
        )

    markdown = mineru_result.markdown
    mineru_metadata = mineru_result.metadata
    logs.append(_log("info", "MinerU 解析成功", char_count=len(markdown), elapsed_s=mineru_result.elapsed_s))

    # 3. 组装元数据（图片和表单由 MinerU metadata 提供）
    metadata = {
        "file_name": file_path.name,
        "file_size": file_path.stat().st_size,
        "page_count": mineru_result.page_count,
        "char_count": len(markdown),
    }

    elapsed = round(time.perf_counter() - t0, 2)
    logs.append(_log("info", f"转换完成，耗时 {elapsed}s", elapsed_s=elapsed))

    return ConversionResult(
        markdown=markdown, metadata=metadata, images=[],
        success=bool(markdown), error=None if markdown else "文字提取失败",
        logs=logs, mineru_metadata=mineru_metadata,
    )


def _log(level: str, message: str, **kwargs) -> dict:
    """生成日志条目"""
    import datetime
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "level": level,
        "message": message,
    }
    entry.update(kwargs)
    return entry


