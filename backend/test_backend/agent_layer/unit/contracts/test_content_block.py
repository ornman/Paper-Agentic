from __future__ import annotations

import json

import pytest
from pydantic import TypeAdapter

from app.agent_layer.contracts.content_block import (
    BlockCitation,
    BlockCitationText,
    BlockCode,
    BlockDivider,
    BlockHeading,
    BlockList,
    BlockParagraph,
    BlockTable,
    ContentBlock,
)

ta = TypeAdapter(ContentBlock)


class TestBlockParagraph:
    def test_basic(self):
        block = BlockParagraph(text="hello")
        assert block.type == "paragraph"
        assert block.text == "hello"
        assert block.citations is None

    def test_with_citations(self):
        block = BlockParagraph(
            text="hello", citations=[BlockCitation(sourceId="s1")]
        )
        assert len(block.citations) == 1
        assert block.citations[0].sourceId == "s1"

    def test_serialize(self):
        block = BlockParagraph(text="hello")
        data = block.model_dump()
        assert data == {"type": "paragraph", "text": "hello", "citations": None}

    def test_deserialize(self):
        raw = {"type": "paragraph", "text": "hello"}
        block = BlockParagraph.model_validate(raw)
        assert block.text == "hello"


class TestBlockHeading:
    def test_valid_levels(self):
        for level in [1, 2, 3, 4]:
            block = BlockHeading(level=level, text="title")
            assert block.level == level

    def test_serialize(self):
        block = BlockHeading(level=2, text="title")
        data = block.model_dump()
        assert data == {"type": "heading", "level": 2, "text": "title"}


class TestBlockList:
    def test_unordered(self):
        block = BlockList(ordered=False, items=["a", "b"])
        assert block.ordered is False

    def test_ordered(self):
        block = BlockList(ordered=True, items=["a", "b"])
        assert block.ordered is True


class TestBlockCitationText:
    def test_basic(self):
        block = BlockCitationText(text="ref", sourceIds=["s1", "s2"])
        assert block.type == "citation_block"
        assert len(block.sourceIds) == 2


class TestBlockTable:
    def test_basic(self):
        block = BlockTable(
            headers=["col1", "col2"], rows=[["a", "b"], ["c", "d"]]
        )
        assert len(block.rows) == 2
        assert block.headers == ["col1", "col2"]


class TestBlockCode:
    def test_basic(self):
        block = BlockCode(language="python", code="print('hi')")
        assert block.type == "code"
        assert block.language == "python"
        assert block.code == "print('hi')"


class TestBlockDivider:
    def test_basic(self):
        block = BlockDivider()
        assert block.type == "divider"


class TestDiscriminatedUnion:
    def test_paragraph_route(self):
        raw = {"type": "paragraph", "text": "hello"}
        result = ta.validate_python(raw)
        assert isinstance(result, BlockParagraph)

    def test_heading_route(self):
        raw = {"type": "heading", "level": 1, "text": "title"}
        result = ta.validate_python(raw)
        assert isinstance(result, BlockHeading)

    def test_list_route(self):
        raw = {"type": "list", "ordered": False, "items": ["a"]}
        result = ta.validate_python(raw)
        assert isinstance(result, BlockList)

    def test_citation_block_route(self):
        raw = {"type": "citation_block", "text": "ref", "sourceIds": ["s1"]}
        result = ta.validate_python(raw)
        assert isinstance(result, BlockCitationText)

    def test_table_route(self):
        raw = {"type": "table", "headers": ["h"], "rows": [["r"]]}
        result = ta.validate_python(raw)
        assert isinstance(result, BlockTable)

    def test_code_route(self):
        raw = {"type": "code", "language": "py", "code": "x=1"}
        result = ta.validate_python(raw)
        assert isinstance(result, BlockCode)

    def test_divider_route(self):
        raw = {"type": "divider"}
        result = ta.validate_python(raw)
        assert isinstance(result, BlockDivider)

    def test_invalid_type_raises(self):
        with pytest.raises(Exception):
            ta.validate_python({"type": "unknown"})


class TestContentBlockJson:
    def test_dump_paragraph(self):
        block = BlockParagraph(text="hello")
        json_str = ta.dump_json(block).decode()
        data = json.loads(json_str)
        assert data["type"] == "paragraph"
        assert data["text"] == "hello"

    def test_dump_citation_block(self):
        block = BlockCitationText(text="ref", sourceIds=["s1"])
        json_str = ta.dump_json(block).decode()
        data = json.loads(json_str)
        assert data["type"] == "citation_block"
        assert data["sourceIds"] == ["s1"]

    def test_roundtrip(self):
        blocks: list[ContentBlock] = [
            BlockParagraph(text="p"),
            BlockHeading(level=1, text="h"),
            BlockList(ordered=False, items=["i"]),
            BlockCitationText(text="c", sourceIds=["s"]),
            BlockTable(headers=["h"], rows=[["r"]]),
            BlockCode(language="py", code="x"),
            BlockDivider(),
        ]
        for block in blocks:
            json_bytes = ta.dump_json(block)
            restored = ta.validate_json(json_bytes)
            assert restored == block
