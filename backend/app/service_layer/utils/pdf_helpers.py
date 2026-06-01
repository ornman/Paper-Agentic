"""PDF 文件辅助工具（元数据提取、页数、文件大小、哈希）"""

from __future__ import annotations

import hashlib
from pathlib import Path


def read_pdf_page_count(file_path: Path) -> int:
    """尝试从 PDF 文件读取实际页数，失败返回 0"""
    try:
        import pypdf

        with open(file_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            return len(reader.pages)
    except Exception:
        return 0


def read_file_size(file_path: Path) -> int:
    """从文件系统读取文件大小"""
    try:
        return file_path.stat().st_size
    except Exception:
        return 0


def compute_file_hash(file_path: Path) -> str:
    """计算文件 SHA-256 前 16 位"""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def extract_pdf_metadata(file_path: Path) -> dict:
    """从 PDF 文件提取元数据（标题、作者、年份）"""
    result: dict = {"title": "", "authors": "", "year": None}
    try:
        import pypdf

        with open(file_path, "rb") as f:
            meta = pypdf.PdfReader(f).metadata
            if not meta:
                return result
            title = (meta.title or "").strip()
            if title:
                result["title"] = title
            author = (meta.author or "").strip()
            if author:
                result["authors"] = author
            for date_field in (meta.get("/CreationDate", ""), meta.get("/ModDate", "")):
                if isinstance(date_field, str) and date_field.startswith("D:"):
                    try:
                        result["year"] = int(date_field[2:6])
                    except (ValueError, IndexError):
                        pass
                    break
    except Exception:
        pass
    return result
