"""文档导入 API — 前端兼容路由（含 SSE 进度流）"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile, File as FastAPIFile
from fastapi.responses import StreamingResponse

from app.data_layer.contracts.library_item import ImportTask, LibraryItem
from app.service_layer.schemas.library import ImportStartResponse, ImportStatusResponse

logger = logging.getLogger("paper-assistant")

router = APIRouter(tags=["import"])


@router.post("/import/start", response_model=ImportStartResponse)
async def start_import(file: UploadFile = FastAPIFile(...), request: Request = None):
    container = request.app.state.container

    # 保存上传文件
    uploads_dir = Path(container.settings.uploads_dir)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    dest = uploads_dir / (file.filename or "upload.pdf")
    content = await file.read()
    dest.write_bytes(content)

    # 格式校验
    if dest.suffix.lower() != ".pdf":
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="仅支持 PDF 格式")

    # 去重检查
    file_hash = _compute_file_hash(dest)
    existing = container.library_repo.get_by_hash(file_hash)
    if existing:
        return ImportStartResponse(task_id="", status="duplicate")

    task_id = uuid.uuid4().hex[:12]
    task = ImportTask(task_id=task_id, file_path=str(dest))
    container.import_task_repo.create(task)

    asyncio.create_task(_run_import_with_progress(container, task_id, dest))

    return ImportStartResponse(task_id=task_id, status="queued")


@router.get("/import/status/{task_id}", response_model=ImportStatusResponse)
async def get_import_status(task_id: str, request: Request):
    container = request.app.state.container
    task = container.import_task_repo.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="导入任务不存在")

    file_name = Path(task.file_path).name if task.file_path else None
    return ImportStatusResponse(
        task_id=task.task_id,
        paper_id=task.paper_id or None,
        status=task.status,
        current_step=task.status,
        error_msg=task.message or None,
        file_name=file_name,
    )


@router.get("/import/stream/{task_id}")
async def stream_import_progress(task_id: str, request: Request):
    container = request.app.state.container
    bus = container.import_progress_bus
    q = bus.subscribe(task_id)

    async def event_generator():
        try:
            while True:
                event = await asyncio.wait_for(q.get(), timeout=300)
                yield f"event: progress\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("status") in ("completed", "failed", "done"):
                    break
        except asyncio.TimeoutError:
            yield f"event: progress\ndata: {json.dumps({'status': 'timeout'}, ensure_ascii=False)}\n\n"
        finally:
            bus.unsubscribe(task_id, q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _run_import_with_progress(container, task_id: str, file_path: Path):
    """后台导入 worker（带进度推送）"""
    bus = container.import_progress_bus

    async def publish(event: dict):
        await bus.publish(task_id, event)

    try:
        container.import_task_repo.update_status(task_id, "running")
        await publish({"status": "running", "step": "starting", "paper_id": None})

        from app.data_layer.preprocessing.transfer.pipeline import PipelineOrchestrator

        loop = asyncio.get_event_loop()

        def on_stage(pipeline_event):
            asyncio.run_coroutine_threadsafe(
                publish({"status": "running", "step": pipeline_event.stage.value, "paper_id": None}),
                loop,
            )

        orchestrator = PipelineOrchestrator(
            monitor_callback=on_stage,
            embedding_client=container.embedding_client,
            vector_index=container.vector_store,
            keyword_index=container.keyword_search,
        )

        result = await container.document_ingest.ingest_document(
            file_path, pipeline_orchestrator=orchestrator,
        )

        if result.success:
            container.import_task_repo.update_status(
                task_id, "completed", message=f"导入成功，{result.chunk_count} 个 chunk", paper_id=result.paper_id,
            )
            container.library_repo.upsert(LibraryItem(
                item_id=result.paper_id,
                title=file_path.stem,
                file_path=str(file_path),
                file_type=file_path.suffix.lower(),
                status="ready",
            ))
            await publish({"status": "completed", "step": "done", "paper_id": result.paper_id})
        else:
            container.import_task_repo.update_status(task_id, "failed", message=result.error or "导入失败")
            await publish({"status": "failed", "step": "error", "error_msg": result.error})
    except Exception as e:
        logger.error("后台导入失败 [%s]: %s", task_id, e, exc_info=True)
        container.import_task_repo.update_status(task_id, "failed", message=str(e))
        await publish({"status": "failed", "step": "error", "error_msg": str(e)})
    finally:
        await publish({"status": "done", "step": None, "paper_id": None})


def _compute_file_hash(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]
