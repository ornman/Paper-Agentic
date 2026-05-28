"""文档转换器

MinerU 精准解析 API 为主链路，支持 PDF/DOCX/DOC/PPTX/XLSX 等多格式。
MinerU 失败即为转换失败，不保留低质量降级路径。

输出：markdown + metadata + 图片路径列表 + 处理日志
"""

from __future__ import annotations

import logging
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
        file_path: 文件路径（PDF/DOCX/DOC/PPTX/XLSX 等）
        output_dir: 图片输出目录
        on_mineru_progress: MinerU 进度回调
    """
    if not file_path.exists():
        return ConversionResult(
            markdown="",
            metadata={},
            images=[],
            success=False,
            error=f"文件不存在: {file_path}",
            logs=[_log("error", "文件不存在", file_path=str(file_path))],
        )

    logs: list[dict] = []
    t0 = time.perf_counter()

    # 1. MinerU 解析（超限切分由 MinerUClient 自动处理）
    logs.append(_log("info", "MinerU 解析"))
    from .mineru_adapter import convert_with_mineru

    mineru_result = await convert_with_mineru(
        file_path,
        on_progress=on_mineru_progress,
    )

    if not mineru_result.success:
        logs.append(_log("error", f"MinerU 解析失败: {mineru_result.error}"))
        return ConversionResult(
            markdown="",
            metadata={},
            images=[],
            success=False,
            error=mineru_result.error,
            logs=logs,
        )

    markdown = mineru_result.markdown
    mineru_metadata = mineru_result.metadata
    logs.append(_log("info", "MinerU 解析成功", char_count=len(markdown), elapsed_s=mineru_result.elapsed_s))

    is_pdf = file_path.suffix.lower() == ".pdf"

    # 2. 提取图片（仅 PDF — pdf2image 不支持其他格式）
    images: list[dict] = []
    if is_pdf and output_dir:
        logs.append(_log("info", "开始图片提取"))
        images = _extract_images(file_path, output_dir)
        logs.append(_log("info", f"图片提取完成，共 {len(images)} 张"))

    # 3. 提取表单（仅 PDF — pypdf 不支持其他格式）
    form_fields: list[dict] = []
    if is_pdf:
        logs.append(_log("info", "开始表单提取"))
        form_fields = _extract_form_fields(file_path)
        logs.append(_log("info", f"表单提取完成，共 {len(form_fields)} 个字段"))

    # 4. 组装元数据
    page_count = mineru_result.page_count

    metadata = {
        "file_name": file_path.name,
        "file_size": file_path.stat().st_size,
        "page_count": page_count,
        "form_fields": form_fields,
        "char_count": len(markdown),
    }

    elapsed = round(time.perf_counter() - t0, 2)
    logs.append(_log("info", f"转换完成，耗时 {elapsed}s", elapsed_s=elapsed))

    return ConversionResult(
        markdown=markdown,
        metadata=metadata,
        images=images,
        success=bool(markdown),
        error=None if markdown else "文字提取失败",
        logs=logs,
        mineru_metadata=mineru_metadata,
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


def _extract_images(file_path: Path, output_dir: Path) -> list[dict]:
    """将 PDF 页面转为图片"""
    try:
        from pdf2image import convert_from_path

        output_dir.mkdir(parents=True, exist_ok=True)
        images = convert_from_path(
            str(file_path),
            dpi=150,
            output_folder=str(output_dir),
            fmt="png",
            paths_only=True,
            poppler_path=None,
        )

        result = []
        for i, img_path in enumerate(images):
            result.append({
                "page": i + 1,
                "path": str(img_path),
            })
        return result

    except ImportError:
        logger.warning("pdf2image 未安装，跳过图片提取")
        return []
    except Exception as e:
        logger.warning("图片提取失败: %s", e)
        return []


def _extract_form_fields(file_path: Path) -> list[dict]:
    """提取 PDF 表单字段"""
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(file_path))
        fields = reader.get_fields()
        if not fields:
            return []

        result = []
        for field_id, field_obj in fields.items():
            ft = field_obj.get("/FT", "")
            field_info = {
                "field_id": field_id,
                "type": _field_type_name(ft),
            }
            if "/V" in field_obj:
                field_info["default_value"] = str(field_obj["/V"])
            result.append(field_info)

        return result

    except Exception as e:
        logger.warning("表单字段提取失败: %s", e)
        return []


def _field_type_name(ft: str) -> str:
    """表单字段类型名称"""
    mapping = {
        "/Tx": "text",
        "/Btn": "button",
        "/Ch": "choice",
        "/Sig": "signature",
    }
    return mapping.get(ft, "unknown")
