"""导入 API 路由"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from sqlalchemy import text
from starlette.responses import StreamingResponse

from app.api.v1.deps import get_sqlite
from app.core.config import get_settings
from app.core.errors import AppError, ImportFailedError
from app.pipelines.ingestion.service import IngestionService

router = APIRouter(prefix="/import", tags=["import"])
logger = logging.getLogger("paper-assistant")

_ingest_service: IngestionService | None = None


STAGE_PERCENT = {
    "pending": 3,
    "queued": 8,
    "parsing": 18,
    "vlm": 34,
    "cleaning": 52,
    "chunking": 64,
    "embedding": 78,
    "storing": 92,
    "completed": 100,
    "failed": 100,
    "error": 100,
}


def _get_service() -> IngestionService:
    global _ingest_service
    if _ingest_service is None:
        _ingest_service = IngestionService()
    return _ingest_service


def _format_progress_payload(row: tuple[str, str | None, str | None, str | None, str | None]) -> dict:
    status, step, paper_id, error_msg, file_path = row
    file_name = Path(file_path).name if file_path else None
    return {
        "status": status,
        "current_step": step,
        "paper_id": paper_id,
        "error_msg": error_msg,
        "file_name": file_name,
        "percent": STAGE_PERCENT.get(status, 0),
    }


@router.post("/start")
async def start_import(file: UploadFile = File(...)):
    """启动异步导入任务"""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise AppError(1001, "只支持 PDF 文件")

    task_id = uuid.uuid4().hex[:12]
    uploads_dir = Path(get_settings().uploads_dir)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    upload_path = uploads_dir / f"{task_id}_{Path(file.filename).name}"

    with open(upload_path, "wb") as output_file:
        output_file.write(await file.read())

    upload_path_str = str(upload_path)
    IngestionService._log(task_id, upload_path_str, "queued", "任务已创建，等待处理")
    service = _get_service()

    async def _run():
        try:
            await service.ingest_pdf(upload_path_str, task_id)
        except ImportFailedError as exc:
            logger.warning("导入任务阶段失败: %s - %s", task_id, exc.detail["message"])
        except Exception as exc:
            logger.exception("导入任务失败: %s", task_id)
            IngestionService._log(task_id, upload_path_str, "error", "导入失败", error_msg=str(exc))

    asyncio.create_task(_run())
    return {"task_id": task_id, "status": "started"}


@router.get("/status/{task_id}")
async def get_import_status(task_id: str):
    """查询导入状态"""
    sqlite = get_sqlite()
    with sqlite.get_session() as session:
        result = session.execute(
            text(
                "SELECT status, current_step, paper_id, error_msg, file_path "
                "FROM import_logs WHERE task_id = :tid"
            ),
            {"tid": task_id},
        )
        row = result.fetchone()

    if not row:
        raise AppError(2001, f"任务不存在: {task_id}")

    return {"task_id": task_id, **_format_progress_payload(row)}


@router.get("/stream/{task_id}")
async def stream_import(task_id: str):
    """SSE 实时推送导入进度"""

    async def event_generator():
        sqlite = get_sqlite()
        missing_checks = 0

        while True:
            with sqlite.get_session() as session:
                result = session.execute(
                    text(
                        "SELECT status, current_step, paper_id, error_msg, file_path "
                        "FROM import_logs WHERE task_id = :tid"
                    ),
                    {"tid": task_id},
                )
                row = result.fetchone()

            if not row:
                missing_checks += 1
                if missing_checks < 10:
                    await asyncio.sleep(0.2)
                    continue
                yield f"event: error\ndata: {json.dumps({'message': '任务不存在'})}\n\n"
                return

            missing_checks = 0
            yield f"data: {json.dumps(_format_progress_payload(row))}\n\n"

            if row[0] in ("completed", "failed", "error"):
                break

            await asyncio.sleep(0.6)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
