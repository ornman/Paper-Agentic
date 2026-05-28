from __future__ import annotations

from app.agent_layer.contracts.content_block import (
    BlockCitation,
    BlockDivider,
    BlockHeading,
    BlockList,
    BlockParagraph,
    BlockTable,
)
from app.agent_layer.contracts.source_card import SourceCard
from app.agent_layer.response.block_streamer import stream_to_blocks


def test_heading():
    blocks = stream_to_blocks("# 标题一\n## 标题二", [])
    assert len(blocks) == 2
    assert isinstance(blocks[0], BlockHeading)
    assert blocks[0].level == 1
    assert blocks[0].text == "标题一"
    assert isinstance(blocks[1], BlockHeading)
    assert blocks[1].level == 2
    assert blocks[1].text == "标题二"


def test_unordered_list():
    blocks = stream_to_blocks("- 项目一\n- 项目二\n- 项目三", [])
    assert len(blocks) == 1
    assert isinstance(blocks[0], BlockList)
    assert blocks[0].ordered is False
    assert blocks[0].items == ["项目一", "项目二", "项目三"]


def test_ordered_list():
    blocks = stream_to_blocks("1. 第一步\n2. 第二步\n3. 第三步", [])
    assert len(blocks) == 1
    assert isinstance(blocks[0], BlockList)
    assert blocks[0].ordered is True
    assert len(blocks[0].items) == 3


def test_table():
    text = "| A | B |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |"
    blocks = stream_to_blocks(text, [])
    assert len(blocks) == 1
    assert isinstance(blocks[0], BlockTable)
    assert blocks[0].headers == ["A", "B"]
    assert blocks[0].rows == [["1", "2"], ["3", "4"]]


def test_divider():
    blocks = stream_to_blocks("---", [])
    assert len(blocks) == 1
    assert isinstance(blocks[0], BlockDivider)


def test_paragraph():
    blocks = stream_to_blocks("这是一段普通文本", [])
    assert len(blocks) == 1
    assert isinstance(blocks[0], BlockParagraph)
    assert blocks[0].text == "这是一段普通文本"
    assert blocks[0].citations is None


def test_paragraph_with_citations():
    sources = [SourceCard(id="src_1", title="论文A")]
    blocks = stream_to_blocks("研究表明[1]该方法有效", sources)
    assert len(blocks) == 1
    assert isinstance(blocks[0], BlockParagraph)
    assert blocks[0].text == "研究表明该方法有效"
    assert blocks[0].citations is not None
    assert len(blocks[0].citations) == 1
    assert blocks[0].citations[0].sourceId == "src_1"


def test_mixed_content():
    text = "# 标题\n\n正文段落\n\n- 列表项\n\n---"
    blocks = stream_to_blocks(text, [])
    types = [type(b).__name__ for b in blocks]
    assert "BlockHeading" in types
    assert "BlockParagraph" in types
    assert "BlockList" in types
    assert "BlockDivider" in types
