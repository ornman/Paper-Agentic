"""PDF 拆分工具

从旧 mineru_client.py 提取的纯函数：页数探测、切分计算、临时文件生成。
"""

from __future__ import annotations

import tempfile
from pathlib import Path


def _get_settings():
    from app.service_layer.config.settings import get_settings
    return get_settings()


def _max_pages_per_chunk() -> int:
    return _get_settings().mineru_max_pages_per_chunk


def _max_file_size_bytes() -> int:
    return 190 * 1024 * 1024


def get_pdf_page_count(file_path: Path) -> int:
    """获取 PDF 页数。非 PDF 返回 0。"""
    if file_path.suffix.lower() != ".pdf":
        return 0
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(file_path))
        return len(reader.pages)
    except Exception:
        return 0


def needs_split(file_path: Path, page_ranges: str | None = None) -> bool:
    """判断是否需要切分"""
    if file_path.suffix.lower() != ".pdf":
        return False
    if page_ranges is not None:
        return False
    page_count = get_pdf_page_count(file_path)
    file_size = file_path.stat().st_size
    return page_count > _max_pages_per_chunk() or file_size > _max_file_size_bytes()


def compute_chunks(total_pages: int, max_pages: int = 0) -> list[str]:
    """计算切分段的页码范围列表

    Returns:
        ["1-180", "181-360", ...] 格式
    """
    if not max_pages:
        max_pages = _max_pages_per_chunk()
    chunks = []
    start = 1
    while start <= total_pages:
        end = min(start + max_pages - 1, total_pages)
        chunks.append(f"{start}-{end}")
        start = end + 1
    return chunks


def parse_page_range(range_str: str) -> tuple[int, int]:
    """解析 "1-180" 为 (1, 180)"""
    parts = range_str.split("-")
    return int(parts[0]), int(parts[1])


def split_pdf(file_path: Path, chunk_range: str) -> Path:
    """提取指定页码范围到临时 PDF 文件

    Returns:
        临时 PDF 文件路径（调用方负责清理）
    """
    from pypdf import PdfReader, PdfWriter

    start, end = parse_page_range(chunk_range)
    reader = PdfReader(str(file_path))
    writer = PdfWriter()
    for p in range(start - 1, end):
        writer.add_page(reader.pages[p])

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp_path = Path(tmp.name)
    writer.write(tmp)
    tmp.close()
    return tmp_path


def adjust_content_list_page_idx(
    content_list: list[dict],
    offset: int,
) -> list[dict]:
    """调整 content_list 中所有条目的 page_idx 偏移（返回新列表）"""
    if offset == 0:
        return content_list
    return [
        {**item, "page_idx": item["page_idx"] + offset}
        if "page_idx" in item else item
        for item in content_list
    ]
