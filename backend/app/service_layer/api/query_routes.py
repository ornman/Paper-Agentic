"""POST /api/v1/query — Agent 层对话入口"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.agent_layer.contracts.query import AskRequest
from app.agent_layer.orchestration.turn_runner import TurnRunner
from app.agent_layer.planning.retrieval_gate import should_retrieve
from app.agent_layer.planning.snapshot_builder import build_snapshot
from app.agent_layer.response.block_streamer import stream_to_blocks
from app.agent_layer.response.source_mapper import map_sources
from app.agent_layer.runtime.chat_model import ChatModel
from app.agent_layer.session.editor_context_store import EditorContextStore
from app.agent_layer.session.persistence import SessionPersistence
from app.agent_layer.session.window_store import ConversationWindowStore
from app.service_layer.config.settings import get_settings

logger = logging.getLogger("paper-assistant")

router = APIRouter()

_window_store = ConversationWindowStore(max_messages=20)
_editor_context_store = EditorContextStore()
_persistence = SessionPersistence()


def _build_runner(settings=None) -> TurnRunner:
    s = settings or get_settings()
    chat_model = ChatModel(s)
    return TurnRunner(
        chat_model=chat_model,
        snapshot_builder=build_snapshot,
        retrieval_gate=should_retrieve,
        source_mapper=map_sources,
        block_streamer=stream_to_blocks,
        window_store=_window_store,
        editor_context_store=_editor_context_store,
        persistence=_persistence,
    )


@router.post("/query")
async def query_endpoint(body: AskRequest, request: Request):
    runner = _build_runner()

    async def event_stream():
        async for frame in runner.run(body):
            yield frame

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
