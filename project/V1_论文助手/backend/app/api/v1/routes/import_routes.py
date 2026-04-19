"""导入 API 路由"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, UploadFile, File
from starlette.responses import StreamingResponse

from app.api.v1.deps import get_sqlite
from app.core.errors import AppError
from app.pipelines.ingestion.service import IngestionService
from sqlalchemy import text

router = APIRouter(prefix="/import", tags=["import"])
logger = logging.getLogger("paper-assistant")

_ingest_service: IngestionService | None = None
_active_tasks: dict[str, asyncio.Task] = {}


def _get_service() -> IngestionService:
    global _ingest_service
    if _ingest_service is None:
        _ingest_service = IngestionService()
    return _ingest_service


@router.post("/start")
async def start_import(file: UploadFile = File(...)):
    """启动异步导入任务"""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise AppError(1001, "只支持 PDF 文件")

    task_id = uuid.uuid4().hex[:12]

    # 保存上传文件
    os.makedirs("./data/uploads", exist_ok=True)
    upload_path = f"./data/uploads/{task_id}_{file.filename}"
    with open(upload_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # 后台异步执行
    progress_queue: asyncio.Queue = asyncio.Queue()
    service = _get_service()

    async def _run():
        async def progress_cb(stage, msg, data=None):
            await progress_queue.put({"stage": stage, "message": msg, "data": data})

        try:
            await service.ingest_pdf(upload_path, task_id, progress_cb)
        except Exception as e:
            await progress_queue.put({"stage": "error", "message": str(e)})
        finally:
            await progress_queue.put(None)  # sentinel

    task = asyncio.create_task(_run())
    _active_tasks[task_id] = task

    return {"task_id": task_id, "status": "started"}


@router.get("/status/{task_id}")
async def get_import_status(task_id: str):
    """查询导入状态"""
    sqlite = get_sqlite()
    with sqlite.get_session() as session:
        result = session.execute(
            text("SELECT task_id, paper_id, status, current_step, error_msg "
                 "FROM import_logs WHERE task_id = :tid"),
            {"tid": task_id},
        )
        row = result.fetchone()

    if not row:
        raise AppError(2001, f"任务不存在: {task_id}")

    return {
        "task_id": row[0],
        "paper_id": row[1],
        "status": row[2],
        "current_step": row[3],
        "error_msg": row[4],
    }


@router.get("/stream/{task_id}")
async def stream_import(task_id: str):
    """SSE 实时推送导入进度"""
    async def event_generator():
        sqlite = get_sqlite()
        while True:
            with sqlite.get_session() as session:
                result = session.execute(
                    text("SELECT status, current_step, paper_id FROM import_logs WHERE task_id = :tid"),
                    {"tid": task_id},
                )
                row = result.fetchone()

            if not row:
                yield f"event: error\ndata: {json.dumps({'message': '任务不存在'})}\n\n"
                return

            status, step, paper_id = row
            yield f"data: {json.dumps({'status': status, 'step': step, 'paper_id': paper_id})}\n\n"

            if status in ("completed", "failed", "error"):
                break

            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


import os
