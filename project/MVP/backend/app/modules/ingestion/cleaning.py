# MinerU 结果清洗入口（支持图片和完整结构）
#
# 当前实现的清洗规则：
# 1. 页眉页脚过滤
# 2. 页码清理
# 3. 短噪音块过滤
# 4. 重复块过滤
# 5. 图片描述生成（VLM）

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.clients.vlm_client import VLMClient
from app.clients.kimi_client import KimiVLMClient
from app.core.config import get_settings
from app.modules.ingestion.dto import CleanedBlock, CleanedDocument

settings = get_settings()

# 纯页码 / 常见页码格式。
_PAGE_NUMBER_PATTERNS = (
    r"^\d{1,4}$",
    r"^第\s*\d{1,4}\s*页$",
    r"^[Pp]age\s*\d{1,4}$",
    r"^[—\-–]\s*\d{1,4}\s*[—\-–]$",
)

# 带句号的正文大概率不是页眉页脚。
_SENTENCE_PUNCTUATION = set("。！？.!?")

# 过短文本通常是 OCR 噪音、孤立符号、残缺编号。
_MIN_MEANINGFUL_TEXT_LENGTH = 2


def clean_mineru_payload(
    *,
    document_id: str,
    title: str,
    file_path: str,
    index_mode: str,
    payload: dict[str, Any],
) -> CleanedDocument:
    """清洗 MinerU 返回 JSON，保留完整结构（包括图片）并生成图片描述."""
    raw_blocks = _extract_raw_blocks(payload)
    text_page_counts = _count_distinct_pages_by_text(raw_blocks)

    cleaned_blocks: list[CleanedBlock] = []
    seen_texts: set[str] = set()

    # 分离文本块和图片块
    text_blocks = []
    image_blocks = []

    for block in raw_blocks:
        if block.get("block_type") == "image":
            image_blocks.append(block)
        else:
            text_blocks.append(block)

    # 过滤文本块（应用噪音过滤规则）
    for block in text_blocks:
        text = block.get("content", "")

        if _is_header_or_footer(text, text_page_counts):
            continue
        if _is_page_number(text):
            continue
        if _is_short_noise(block):
            continue
        if text in seen_texts:
            continue

        seen_texts.add(text)
        cleaned_blocks.append(
            CleanedBlock(
                block_id=f"{document_id}_block_{len(cleaned_blocks):04d}",
                page=block.get("page", 0),
                block_type=block.get("block_type", "text"),
                content=text,
                bbox=block.get("bbox"),
                image_path=None,
                metadata=block.get("metadata", {}),
            )
        )

    # 为图片块生成描述
    if image_blocks:
        print(f"[CLEANING] 为 {len(image_blocks)} 个图片块生成描述...")
        described_images = asyncio.run(_describe_images(
            document_id,
            file_path,
            image_blocks,
        ))
        cleaned_blocks.extend(described_images)

    return CleanedDocument(
        document_id=document_id,
        title=title,
        file_path=file_path,
        index_mode=index_mode,
        blocks=cleaned_blocks,
        raw_block_count=len(raw_blocks),
        cleaned_block_count=len(cleaned_blocks),
        removed_block_count=len(raw_blocks) - len(cleaned_blocks),
    )


def _extract_raw_blocks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """从 MinerU payload 中提取所有块（包括文本和图片）."""
    pages = payload.get("pages")
    if not isinstance(pages, list):
        return []

    raw_blocks: list[dict[str, Any]] = []

    for page_item in pages:
        if not isinstance(page_item, dict):
            continue

        page_number = page_item.get("page")
        if not isinstance(page_number, int):
            continue

        blocks = page_item.get("blocks")
        if not isinstance(blocks, list):
            continue

        for block in blocks:
            extracted_block = _extract_block_info(page_number, block)
            if extracted_block:
                raw_blocks.append(extracted_block)

    return raw_blocks


def _extract_block_info(page: int, block: dict[str, Any]) -> dict[str, Any] | None:
    """从 block 中提取信息，支持文本和图片（处理嵌套结构）."""
    if not isinstance(block, dict):
        return None

    block_type = block.get("type", "text")

    # 处理图片块（嵌套结构）：type可能是image、table、figure等
    if block_type in ("image", "table", "figure", "picture"):
        image_path = _extract_image_path(block)
        if image_path:
            return {
                "page": page,
                "block_type": "image",
                "content": "",  # 稍后填充 VLM 描述
                "bbox": block.get("bbox"),
                "image_path": image_path,
                "metadata": {"raw_block_type": block_type, "raw_block": block},
            }

    # 处理文本块（嵌套结构：lines[0].spans[N].content）
    text = _read_block_text_nested(block)
    if text:
        return {
            "page": page,
            "block_type": block_type,
            "content": text,
            "bbox": block.get("bbox"),
            "image_path": None,
            "metadata": {},
        }

    return None


def _read_block_text_nested(block: dict[str, Any]) -> str:
    """从嵌套结构中提取文本（lines[0].spans[N].content）."""
    if not isinstance(block, dict):
        return ""

    # 检查嵌套结构 lines[0].spans
    lines = block.get("lines")
    if isinstance(lines, list) and lines:
        first_line = lines[0]
        if isinstance(first_line, dict):
            spans = first_line.get("spans")
            if isinstance(spans, list):
                # 拼接所有 span 的 content
                text_parts = []
                for span in spans:
                    if isinstance(span, dict):
                        # 优先使用 content 字段
                        content = span.get("content") or span.get("text", "")
                        if isinstance(content, str):
                            text_parts.append(content)
                        elif isinstance(content, list):
                            # 处理特殊情况：content 是列表
                            text_parts.extend(str(c) for c in content)

                if text_parts:
                    return " ".join(text_parts)

    # 回退到旧方法（检查直接字段）
    return _read_block_text(block)


def _read_block_text(block: Any) -> str:
    """兼容多种常见字段名，并做统一文本规范化."""
    if not isinstance(block, dict):
        return ""

    for field_name in ("text", "content", "markdown", "md"):
        value = block.get(field_name)
        if isinstance(value, str):
            return _normalize_text(value)
    return ""


def _extract_image_path(block: dict[str, Any]) -> str | None:
    """从图片块中提取图片路径."""
    # 检查直接字段
    if "img_path" in block:
        return block["img_path"]

    # 检查嵌套结构 blocks[0].lines[0].spans[0].image_path
    # 这个结构适用于table、image等类型
    blocks = block.get("blocks")
    if isinstance(blocks, list) and blocks:
        first_block = blocks[0]
        if isinstance(first_block, dict):
            lines = first_block.get("lines")
            if isinstance(lines, list) and lines:
                first_line = lines[0]
                if isinstance(first_line, dict):
                    spans = first_line.get("spans")
                    if isinstance(spans, list) and spans:
                        for span in spans:
                            if isinstance(span, dict):
                                # 检查是否有image_path字段（适用于table、image等）
                                image_path = span.get("image_path")
                                if image_path:
                                    return f"images/{image_path}"

    return None


def _read_block_text(block: Any) -> str:
    """兼容多种常见字段名，并做统一文本规范化."""
    if not isinstance(block, dict):
        return ""

    for field_name in ("text", "content", "markdown", "md"):
        value = block.get(field_name)
        if isinstance(value, str):
            return _normalize_text(value)
    return ""


def _normalize_text(text: str) -> str:
    """归一化空白，避免同一块因空格差异绕过去重."""
    return " ".join(text.split()).strip()


def _count_distinct_pages_by_text(raw_blocks: list[dict[str, Any]]) -> dict[str, int]:
    """统计每段文本出现于多少个不同页面."""
    text_to_pages: dict[str, set[int]] = {}
    for block in raw_blocks:
        if block.get("block_type") == "text":
            text = block.get("content", "")
            if text:
                text_to_pages.setdefault(text, set()).add(block["page"])
    return {text: len(pages) for text, pages in text_to_pages.items()}


def _is_header_or_footer(text: str, text_page_counts: dict[str, int]) -> bool:
    """识别跨页重复的短行页眉页脚."""
    if not isinstance(text, str):
        return False

    if text_page_counts.get(text, 0) < 2:
        return False
    if len(text) > 40:
        return False
    if any(char in _SENTENCE_PUNCTUATION for char in text):
        return False
    return True


def _is_page_number(text: str) -> bool:
    """识别常见页码样式."""
    import re
    return any(re.match(pattern, text) for pattern in _PAGE_NUMBER_PATTERNS)


def _is_short_noise(block: dict[str, Any]) -> bool:
    """过滤极短噪音块."""
    if block.get("block_type") != "text":
        return False
    text = block.get("content", "")
    return len(text) <= _MIN_MEANINGFUL_TEXT_LENGTH


async def _describe_images(
    document_id: str,
    file_path: str,
    image_blocks: list[dict[str, Any]],
) -> list[CleanedBlock]:
    """为图片块生成 VLM 描述."""
    if not image_blocks:
        return []

    vlm_client = KimiVLMClient()
    paper_dir = Path(file_path).parent
    described_blocks = []

    # 提取文档 ID（对应保存的目录名）
    # file_path 格式：D:/.../papers/xxx.pdf
    # 保存的目录格式：data/papers/{task_id}/
    # 这里需要找到对应的 task_id 目录

    # 查找最新的 task_id 目录（假设是最新的）
    papers_dir = Path("./data/papers")
    if not papers_dir.exists():
        print(f"[CLEANING] 警告：papers 目录不存在，跳过图片描述")
        return []

    # 找到包含该 PDF 的目录
    pdf_name = Path(file_path).name
    found_task_dir = None

    for task_dir in sorted(papers_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        # 检查这个目录下是否有对应的 PDF 或图片
        images_dir = task_dir / "images"
        if images_dir.exists():
            # 检查是否有匹配的图片文件
            image_files = list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.png"))
            if image_files:
                found_task_dir = task_dir
                break

    if not found_task_dir:
        print(f"[CLEANING] 警告：未找到 {pdf_name} 的图片目录，跳过图片描述")
        return []

    print(f"[CLEANING] 使用图片目录: {found_task_dir.name}")

    # 为每个图片生成描述
    for i, image_block in enumerate(image_blocks):
        image_path = image_block.get("image_path")
        if not image_path:
            continue

        # 构建完整图片路径
        if image_path.startswith("images/"):
            image_filename = image_path.replace("images/", "")
        else:
            image_filename = image_path

        abs_image_path = found_task_dir / "images" / image_filename

        if not abs_image_path.exists():
            print(f"[CLEANING] 警告：图片不存在 {abs_image_path}")
            continue

        try:
            # 调用 VLM 生成描述
            description = await vlm_client.describe_image(str(abs_image_path))

            described_blocks.append(
                CleanedBlock(
                    block_id=f"{document_id}_image_{i:04d}",
                    page=image_block.get("page", 0),
                    block_type="image",
                    content=description,
                    bbox=image_block.get("bbox"),
                    image_path=image_path,
                    metadata=image_block.get("metadata", {}),
                )
            )
            print(f"[CLEANING] 图片 {i+1}/{len(image_blocks)} 描述完成")

        except Exception as e:
            print(f"[CLEANING] 警告：图片描述失败 {image_path}: {e}")
            # 即使失败也保留图片块，但使用默认描述
            described_blocks.append(
                CleanedBlock(
                    block_id=f"{document_id}_image_{i:04d}",
                    page=image_block.get("page", 0),
                    block_type="image",
                    content="[图片描述不可用]",
                    bbox=image_block.get("bbox"),
                    image_path=image_path,
                    metadata=image_block.get("metadata", {}),
                )
            )

    return described_blocks
