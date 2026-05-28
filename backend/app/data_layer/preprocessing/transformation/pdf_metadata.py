"""从 PDF 文件提取元数据（标题、作者、年份）。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pypdf


@dataclass
class PdfMetadata:
    title: str = ""
    authors: str = ""
    year: str = ""


def extract_pdf_metadata(file_path: str | Path) -> PdfMetadata:
    """从 PDF 的 /Info dict 和文件名提取元数据。"""
    path = Path(file_path)
    if not path.exists():
        return PdfMetadata()

    title = ""
    authors = ""
    year = ""

    try:
        reader = pypdf.PdfReader(str(path))
        info = reader.metadata or {}

        # 标题：优先用 /Title，否则用文件名
        raw_title = info.get("/Title", "")
        if isinstance(raw_title, str) and raw_title.strip():
            title = _clean_text(raw_title)
        if not title:
            title = _title_from_filename(path.stem)

        # 作者
        raw_author = info.get("/Author", "")
        if isinstance(raw_author, str) and raw_author.strip():
            authors = _clean_text(raw_author)

        # 年份：从 /CreationDate 或 /ModDate 提取
        for key in ("/CreationDate", "/ModDate"):
            raw_date = info.get(key, "")
            if isinstance(raw_date, str) and raw_date:
                year = _extract_year(raw_date)
                if year:
                    break

    except Exception:
        # PDF 读取失败时，至少用文件名作标题
        if not title:
            title = _title_from_filename(path.stem)

    return PdfMetadata(title=title, authors=authors, year=year)


def _clean_text(raw: str) -> str:
    """清洗 PDF 元数据中的原始文本。"""
    # 去掉编码前缀（如 feff）
    text = raw.strip()
    if text.startswith("﻿"):
        text = text[1:]
    # 去掉多余空白
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _title_from_filename(stem: str) -> str:
    """将文件名转为可读标题。"""
    # 去掉常见前缀/后缀编号
    name = re.sub(r"^[\d_\-\.]+", "", stem)
    # 空格替换连字符/下划线
    name = name.replace("-", " ").replace("_", " ")
    return name.strip() or stem


def _extract_year(date_str: str) -> str:
    """从 PDF 日期字符串（D:20231225120000+08'00'）提取年份。"""
    match = re.search(r"(\d{4})", date_str)
    if match:
        y = int(match.group(1))
        if 1900 <= y <= 2100:
            return str(y)
    return ""
