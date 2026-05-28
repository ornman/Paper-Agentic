from __future__ import annotations

import json

from app.agent_layer.contracts.content_block import BlockParagraph
from app.agent_layer.contracts.source_card import SourceCard
from app.agent_layer.contracts.sse_events import (
    BlockEvent,
    DoneEvent,
    ErrorEvent,
    SourcesEvent,
    ThinkingEvent,
)


class TestThinkingEvent:
    def test_to_sse_frame(self):
        event = ThinkingEvent(text="思考中...", time_ms=1500)
        frame = event.to_sse_frame()
        assert frame.startswith("event: thinking\n")
        assert "data: " in frame
        assert frame.endswith("\n\n")

    def test_data_payload(self):
        event = ThinkingEvent(text="分析问题", time_ms=2000)
        frame = event.to_sse_frame()
        data_line = [l for l in frame.split("\n") if l.startswith("data: ")][0]
        payload = json.loads(data_line[6:])
        assert payload["text"] == "分析问题"
        assert payload["time_ms"] == 2000

    def test_has_time_ms(self):
        event = ThinkingEvent(text="t", time_ms=0)
        frame = event.to_sse_frame()
        data_line = [l for l in frame.split("\n") if l.startswith("data: ")][0]
        payload = json.loads(data_line[6:])
        assert "time_ms" in payload


class TestBlockEvent:
    def test_to_sse_frame(self):
        block = BlockParagraph(text="hello")
        event = BlockEvent(data=block)
        frame = event.to_sse_frame()
        assert frame.startswith("event: block\n")
        assert frame.endswith("\n\n")

    def test_data_payload(self):
        block = BlockParagraph(text="content")
        event = BlockEvent(data=block)
        frame = event.to_sse_frame()
        data_line = [l for l in frame.split("\n") if l.startswith("data: ")][0]
        payload = json.loads(data_line[6:])
        assert payload["type"] == "paragraph"
        assert payload["text"] == "content"


class TestSourcesEvent:
    def test_to_sse_frame(self):
        sources = [SourceCard(id="s1", title="Paper A")]
        event = SourcesEvent(data=sources)
        frame = event.to_sse_frame()
        assert frame.startswith("event: sources\n")
        assert frame.endswith("\n\n")

    def test_data_payload(self):
        sources = [
            SourceCard(id="s1", title="Paper A"),
            SourceCard(id="s2", title="Paper B", page=5),
        ]
        event = SourcesEvent(data=sources)
        frame = event.to_sse_frame()
        data_line = [l for l in frame.split("\n") if l.startswith("data: ")][0]
        payload = json.loads(data_line[6:])
        assert len(payload) == 2
        assert payload[0]["id"] == "s1"
        assert payload[1]["page"] == 5


class TestDoneEvent:
    def test_to_sse_frame(self):
        event = DoneEvent()
        frame = event.to_sse_frame()
        assert frame.startswith("event: done\n")
        assert "data: {}" in frame
        assert frame.endswith("\n\n")


class TestErrorEvent:
    def test_to_sse_frame(self):
        event = ErrorEvent(message="something went wrong")
        frame = event.to_sse_frame()
        assert frame.startswith("event: error\n")
        assert frame.endswith("\n\n")

    def test_message_in_payload(self):
        event = ErrorEvent(message="timeout")
        frame = event.to_sse_frame()
        data_line = [l for l in frame.split("\n") if l.startswith("data: ")][0]
        payload = json.loads(data_line[6:])
        assert payload["message"] == "timeout"

    def test_chinese_message(self):
        event = ErrorEvent(message="请求超时")
        frame = event.to_sse_frame()
        data_line = [l for l in frame.split("\n") if l.startswith("data: ")][0]
        payload = json.loads(data_line[6:])
        assert payload["message"] == "请求超时"
