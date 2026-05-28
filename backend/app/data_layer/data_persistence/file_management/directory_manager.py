"""文件目录管理器

管理 PDF 文件、图片、产物的目录结构和生命周期。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("paper-assistant")


@dataclass
class DocumentPaths:
    """文档路径结构"""
    paper_id: str
    paper_dir: Path       # data/papers/{paper_id}/
    parsed_dir: Path      # data/parsed/{paper_id}/
    images_dir: Path      # data/parsed/{paper_id}/images/
    markdown_path: Path   # data/parsed/{paper_id}/markdown.json
    structured_path: Path # data/parsed/{paper_id}/structured.json
    report_path: Path     # data/parsed/{paper_id}/extraction_report.json


class DirectoryManager:
    """目录管理器

    管理 papers/、parsed/、backups/ 的目录结构。
    """

    def __init__(
        self,
        papers_dir: str = "./data/papers",
        parsed_dir: str = "./data/parsed",
        backups_dir: str = "./data/backups",
    ):
        self._papers_dir = Path(papers_dir)
        self._parsed_dir = Path(parsed_dir)
        self._backups_dir = Path(backups_dir)

    def init(self):
        """初始化目录结构"""
        self._papers_dir.mkdir(parents=True, exist_ok=True)
        self._parsed_dir.mkdir(parents=True, exist_ok=True)
        self._backups_dir.mkdir(parents=True, exist_ok=True)

    def get_document_paths(self, paper_id: str) -> DocumentPaths:
        """获取文档路径结构

        Args:
            paper_id: 论文 ID

        Returns:
            DocumentPaths
        """
        paper_dir = self._papers_dir / paper_id
        parsed_dir = self._parsed_dir / paper_id
        images_dir = parsed_dir / "images"

        return DocumentPaths(
            paper_id=paper_id,
            paper_dir=paper_dir,
            parsed_dir=parsed_dir,
            images_dir=images_dir,
            markdown_path=parsed_dir / "markdown.json",
            structured_path=parsed_dir / "structured.json",
            report_path=parsed_dir / "extraction_report.json",
        )

    def create_document_dirs(self, paper_id: str) -> DocumentPaths:
        """创建文档目录

        Args:
            paper_id: 论文 ID

        Returns:
            DocumentPaths
        """
        paths = self.get_document_paths(paper_id)

        paths.paper_dir.mkdir(parents=True, exist_ok=True)
        paths.parsed_dir.mkdir(parents=True, exist_ok=True)
        paths.images_dir.mkdir(parents=True, exist_ok=True)

        return paths

    def copy_paper(self, source_path: Path, paper_id: str) -> Path:
        """复制 PDF 到 papers 目录

        Args:
            source_path: 源文件路径
            paper_id: 论文 ID

        Returns:
            目标路径
        """
        paths = self.create_document_dirs(paper_id)
        dest_path = paths.paper_dir / source_path.name

        if not dest_path.exists():
            shutil.copy2(source_path, dest_path)
            logger.info("复制 PDF: %s -> %s", source_path, dest_path)

        return dest_path

    def save_markdown(self, paper_id: str, markdown: str, metadata: dict):
        """保存 markdown 和 metadata

        Args:
            paper_id: 论文 ID
            markdown: markdown 文本
            metadata: 元数据
        """
        paths = self.get_document_paths(paper_id)
        paths.parsed_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "markdown": markdown,
            "metadata": metadata,
        }

        with open(paths.markdown_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info("保存 markdown: %s", paths.markdown_path)

    def save_structured(self, paper_id: str, structured: dict):
        """保存结构化数据

        Args:
            paper_id: 论文 ID
            structured: 结构化数据
        """
        paths = self.get_document_paths(paper_id)
        paths.parsed_dir.mkdir(parents=True, exist_ok=True)

        with open(paths.structured_path, "w", encoding="utf-8") as f:
            json.dump(structured, f, ensure_ascii=False, indent=2)

        logger.info("保存 structured: %s", paths.structured_path)

    def save_report(self, paper_id: str, report: dict):
        """保存提取报告

        Args:
            paper_id: 论文 ID
            report: 提取报告
        """
        paths = self.get_document_paths(paper_id)
        paths.parsed_dir.mkdir(parents=True, exist_ok=True)

        with open(paths.report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info("保存 report: %s", paths.report_path)

    def load_markdown(self, paper_id: str) -> dict | None:
        """加载 markdown 和 metadata

        Args:
            paper_id: 论文 ID

        Returns:
            {"markdown": str, "metadata": dict} 或 None
        """
        paths = self.get_document_paths(paper_id)

        if not paths.markdown_path.exists():
            return None

        try:
            with open(paths.markdown_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("加载 markdown 失败: %s, %s", paper_id, e)
            return None

    def delete_document(self, paper_id: str):
        """删除文档目录

        Args:
            paper_id: 论文 ID
        """
        paper_dir = self._papers_dir / paper_id
        parsed_dir = self._parsed_dir / paper_id

        if paper_dir.exists():
            shutil.rmtree(paper_dir)
            logger.info("删除 paper 目录: %s", paper_dir)

        if parsed_dir.exists():
            shutil.rmtree(parsed_dir)
            logger.info("删除 parsed 目录: %s", parsed_dir)

    def backup_document(self, paper_id: str):
        """备份文档

        Args:
            paper_id: 论文 ID
        """
        import time

        parsed_dir = self._parsed_dir / paper_id
        if not parsed_dir.exists():
            return

        backup_name = f"{paper_id}_{int(time.time())}"
        backup_dir = self._backups_dir / backup_name

        shutil.copytree(parsed_dir, backup_dir)
        logger.info("备份文档: %s -> %s", parsed_dir, backup_dir)

    def get_storage_stats(self) -> dict:
        """获取存储统计"""
        stats = {
            "papers_count": 0,
            "parsed_count": 0,
            "papers_size_mb": 0,
            "parsed_size_mb": 0,
        }

        if self._papers_dir.exists():
            papers = list(self._papers_dir.iterdir())
            stats["papers_count"] = len(papers)
            stats["papers_size_mb"] = sum(
                sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
                for p in papers
            ) / (1024 * 1024)

        if self._parsed_dir.exists():
            parsed = list(self._parsed_dir.iterdir())
            stats["parsed_count"] = len(parsed)
            stats["parsed_size_mb"] = sum(
                sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
                for p in parsed
            ) / (1024 * 1024)

        return stats
