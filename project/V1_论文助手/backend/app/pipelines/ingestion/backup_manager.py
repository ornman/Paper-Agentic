"""导入流程备份管理器：支持断点续传"""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger("paper-assistant")

STAGE_ORDER = ["mineru", "vlm", "cleaning", "chunking", "embedding", "chroma"]


def _is_stage_terminal(stage: str, status: str) -> bool:
    if status == "completed":
        return True
    return stage == "vlm" and status == "skipped"


STAGE_FILES = {
    "mineru": "full.md",
    "vlm": "full_with_desc.md",
    "cleaning": "cleaning.json",
    "chunking": "chunks.json",
    "embedding": "vectors.json",
}


class BackupManager:
    def __init__(self, backup_dir: str | None = None):
        resolved_backup_dir = backup_dir or get_settings().backup_dir
        self._backup_dir = resolved_backup_dir
        os.makedirs(resolved_backup_dir, exist_ok=True)

    def _backup_path(self, file_hash: str) -> str:
        return os.path.join(self._backup_dir, file_hash)

    def _manifest_path(self, file_hash: str) -> str:
        return os.path.join(self._backup_path(file_hash), "backup.json")

    def exists(self, file_hash: str) -> bool:
        return os.path.exists(self._manifest_path(file_hash))

    def get_backup(self, file_hash: str) -> dict | None:
        path = self._manifest_path(file_hash)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def create(self, file_hash: str, original_path: str, paper_id: str, task_id: str | None = None) -> str:
        """创建备份目录，复制 PDF，初始化 backup.json"""
        backup_path = self._backup_path(file_hash)
        os.makedirs(backup_path, exist_ok=True)

        pdf_dest = os.path.join(backup_path, "paper.pdf")
        if not os.path.exists(pdf_dest):
            shutil.copy2(original_path, pdf_dest)

        manifest = {
            "paper_id": paper_id,
            "task_id": task_id,
            "current_stage": None,
            "last_error": None,
            "file_hash": file_hash,
            "original_path": original_path,
            "status": "pending",
            "stages": {stage: "pending" for stage in STAGE_ORDER},
            "metadata": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self._save_manifest(file_hash, manifest)
        logger.info("备份创建: %s", file_hash[:12])
        return backup_path

    def update_stage(
        self,
        file_hash: str,
        stage: str,
        status: str,
        extra: dict | None = None,
        *,
        task_id: str | None = None,
        error_msg: str | None = None,
    ):
        """更新某个阶段的状态"""
        manifest = self.get_backup(file_hash)
        if manifest is None:
            logger.warning("备份不存在: %s", file_hash[:12])
            return

        manifest["stages"][stage] = status
        manifest["current_stage"] = None if _is_stage_terminal(stage, status) else stage
        manifest["last_error"] = error_msg if status == "failed" else manifest.get("last_error")
        manifest["metadata"]["updated_at"] = datetime.now(timezone.utc).isoformat()

        if task_id:
            manifest["task_id"] = task_id

        if extra:
            manifest["metadata"].update(extra)

        if status == "failed":
            manifest["status"] = "failed"
        elif all(_is_stage_terminal(name, stage_status) for name, stage_status in manifest["stages"].items()):
            manifest["status"] = "completed"
            manifest["current_stage"] = None
            manifest["last_error"] = None
        else:
            manifest["status"] = "running"

        self._save_manifest(file_hash, manifest)
        logger.info("备份阶段更新: %s → %s=%s", file_hash[:12], stage, status)

    def save_stage_data(self, file_hash: str, stage: str, data: str | list | dict):
        """保存阶段数据到文件"""
        filename = STAGE_FILES.get(stage, f"{stage}.json")
        dest = os.path.join(self._backup_path(file_hash), filename)

        if isinstance(data, str):
            with open(dest, "w", encoding="utf-8") as f:
                f.write(data)
        else:
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info("阶段数据保存: %s/%s", file_hash[:12], filename)

    def load_stage_data(self, file_hash: str, stage: str) -> str | list | dict | None:
        """加载阶段数据"""
        filename = STAGE_FILES.get(stage, f"{stage}.json")
        path = os.path.join(self._backup_path(file_hash), filename)
        if not os.path.exists(path):
            return None

        if filename.endswith(".md"):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

    def get_resume_stage(self, file_hash: str) -> str | None:
        """获取需要恢复的阶段（第一个非终态阶段）"""
        manifest = self.get_backup(file_hash)
        if manifest is None:
            return None
        for stage in STAGE_ORDER:
            if not _is_stage_terminal(stage, manifest["stages"].get(stage, "pending")):
                return stage
        return None

    def get_pdf_path(self, file_hash: str) -> str | None:
        """获取备份中的 PDF 文件路径"""
        pdf_path = os.path.join(self._backup_path(file_hash), "paper.pdf")
        return pdf_path if os.path.exists(pdf_path) else None

    def delete_backup(self, file_hash: str) -> None:
        """删除整个备份目录"""
        backup_path = Path(self._backup_path(file_hash))
        if not backup_path.exists():
            return
        shutil.rmtree(backup_path)
        logger.info("备份删除: %s", file_hash[:12])

    def _save_manifest(self, file_hash: str, manifest: dict):
        path = self._manifest_path(file_hash)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
