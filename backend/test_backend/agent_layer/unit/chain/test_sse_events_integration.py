"""SSE 事件序列化集成测试 — 验证前端可正确解析"""

from __future__ import annotations

import json

import pytest

from app.agent_layer.contracts.content_block import BlockCitation, BlockParagraph
from app.agent_layer.contracts.source_card import SourceCard
from app.agent_layer.contracts.sse_events import (
    BlockEvent,
    DoneEvent,
    ErrorEvent,
    SourcesEvent,
    ThinkingEvent,
)


# ── ThinkingEvent ────────────────────────────────────────────────────


async def test_thinking_frame_format():
    """thinking 帧格式：event: thinking\\ndata: {"text": "...", "time_ms": N}\\n\\n"""
    frame = ThinkingEvent(text="思考中...", time_ms=1500).to_sse_frame()
    lines = frame.strip().split("\n")
    assert lines[0] == "event: thinking"
    data = json.loads(lines[1].replace("data: ", ""))
    assert data["text"] == "思考中..."
    assert data["time_ms"] == 1500


async def test_thinking_frame_empty_text():
    """thinking 帧支持空 text"""
    frame = ThinkingEvent(text="", time_ms=0).to_sse_frame()
    data_str = frame.split("data: ")[1].strip()
    data = json.loads(data_str)
    assert data["text"] == ""
    assert data["time_ms"] == 0


# ── BlockEvent ───────────────────────────────────────────────────────


async def test_block_frame_format():
    """block 帧 data 是合法 ContentBlock JSON"""
    block = BlockParagraph(
        text="回答内容", citations=[BlockCitation(sourceId="src_1")]
    )
    frame = BlockEvent(data=block).to_sse_frame()
    data_str = frame.split("data: ")[1].strip()
    data = json.loads(data_str)
    assert data["type"] == "paragraph"
    assert data["text"] == "回答内容"
    assert data["citations"][0]["sourceId"] == "src_1"


async def test_block_frame_no_citations():
    """block 帧无 citations 时 citations 为 null"""
    block = BlockParagraph(text="纯文本")
    frame = BlockEvent(data=block).to_sse_frame()
    data_str = frame.split("data: ")[1].strip()
    data = json.loads(data_str)
    assert data["type"] == "paragraph"
    assert data["text"] == "纯文本"
    assert data["citations"] is None


async def test_block_frame_multiple_citations():
    """block 帧支持多个引用"""
    block = BlockParagraph(
        text="多引用",
        citations=[
            BlockCitation(sourceId="src_1"),
            BlockCitation(sourceId="src_2"),
            BlockCitation(sourceId="src_3"),
        ],
    )
    frame = BlockEvent(data=block).to_sse_frame()
    data_str = frame.split("data: ")[1].strip()
    data = json.loads(data_str)
    assert len(data["citations"]) == 3
    assert data["citations"][2]["sourceId"] == "src_3"


# ── SourcesEvent ─────────────────────────────────────────────────────


async def test_sources_frame_format():
    """sources 帧 data 是 SourceCard 数组"""
    sources = [
        SourceCard(id="src_1", title="论文1", page=1),
        SourceCard(id="src_2", title="论文2", page=5),
    ]
    frame = SourcesEvent(data=sources).to_sse_frame()
    data_str = frame.split("data: ")[1].strip()
    data = json.loads(data_str)
    assert len(data) == 2
    assert data[0]["id"] == "src_1"
    assert data[1]["title"] == "论文2"


async def test_sources_frame_empty():
    """空 sources 帧 data 是空数组"""
    frame = SourcesEvent(data=[]).to_sse_frame()
    data_str = frame.split("data: ")[1].strip()
    data = json.loads(data_str)
    assert data == []


async def test_sources_frame_exclude_none():
    """sources 帧 exclude_none — None 字段不出现在 JSON 中"""
    sources = [SourceCard(id="src_1", title="论文1", page=None)]
    frame = SourcesEvent(data=sources).to_sse_frame()
    data_str = frame.split("data: ")[1].strip()
    data = json.loads(data_str)
    assert "page" not in data[0]


# ── ErrorEvent ───────────────────────────────────────────────────────


async def test_error_frame_format():
    """error 帧 data 包含 message"""
    frame = ErrorEvent(message="出了点问题").to_sse_frame()
    data_str = frame.split("data: ")[1].strip()
    data = json.loads(data_str)
    assert "message" in data
    assert data["message"] == "出了点问题"


async def test_error_frame_chinese_message():
    """error 帧支持中文消息"""
    frame = ErrorEvent(message="请提供问题或内容").to_sse_frame()
    data_str = frame.split("data: ")[1].strip()
    data = json.loads(data_str)
    assert data["message"] == "请提供问题或内容"


# ── DoneEvent ────────────────────────────────────────────────────────


async def test_done_frame_format():
    """done 帧 data 是 {}"""
    frame = DoneEvent().to_sse_frame()
    data_str = frame.split("data: ")[1].strip()
    data = json.loads(data_str)
    assert data == {}


# ── 通用格式验证 ─────────────────────────────────────────────────────


async def test_all_events_parseable():
    """所有事件的 to_sse_frame 输出都能被标准 SSE 解析"""
    events = [
        ThinkingEvent(text="t", time_ms=0),
        BlockEvent(data=BlockParagraph(text="b")),
        SourcesEvent(data=[]),
        DoneEvent(),
        ErrorEvent(message="e"),
    ]
    for event in events:
        frame = event.to_sse_frame()
        assert frame.startswith("event: "), f"Frame should start with 'event: ': {frame!r}"
        assert "\ndata: " in frame, f"Frame should contain '\\ndata: ': {frame!r}"
        assert frame.endswith("\n\n"), f"Frame should end with '\\n\\n': {frame!r}"


async def test_all_events_data_is_valid_json():
    """所有事件的 data 部分是合法 JSON"""
    events = [
        ThinkingEvent(text="思考", time_ms=100),
        BlockEvent(data=BlockParagraph(text="回答")),
        SourcesEvent(
            data=[SourceCard(id="src_1", title="论文", page=1)]
        ),
        DoneEvent(),
        ErrorEvent(message="错误"),
    ]
    for event in events:
        frame = event.to_sse_frame()
        data_line = [
            line for line in frame.split("\n") if line.startswith("data: ")
        ][0]
        data_str = data_line[6:]  # 去掉 "data: "
        parsed = json.loads(data_str)  # 不应抛异常
        assert parsed is not None
