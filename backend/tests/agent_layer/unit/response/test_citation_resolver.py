from __future__ import annotations

from app.agent_layer.contracts.content_block import BlockCitation, BlockParagraph
from app.agent_layer.contracts.source_card import SourceCard
from app.agent_layer.response.citation_resolver import (
    build_citation_map,
    extract_citations,
    inject_citations,
)


def test_extract_citations_multiple():
    text = "研究表明[1]方法有效[2][3]"
    result = extract_citations(text)
    assert len(result) == 3
    assert result[0] == (4, 7, 1)
    assert result[1] == (11, 14, 2)
    assert result[2] == (14, 17, 3)


def test_extract_citations_none():
    assert extract_citations("没有引用的文本") == []


def test_extract_citations_single():
    text = "参考文献[5]"
    result = extract_citations(text)
    assert len(result) == 1
    assert result[0][2] == 5


def test_build_citation_map():
    citations = [(0, 3, 1), (5, 8, 2)]
    sources = [
        SourceCard(id="src_a", title="A"),
        SourceCard(id="src_b", title="B"),
    ]
    mapping = build_citation_map(citations, sources)
    assert mapping == {1: "src_a", 2: "src_b"}


def test_build_citation_map_out_of_range():
    citations = [(0, 3, 5)]
    sources = [SourceCard(id="src_a", title="A")]
    mapping = build_citation_map(citations, sources)
    assert mapping == {}


def test_inject_citations_with_refs():
    text = "研究表明[1]该方法有效"
    citations = [(4, 7, 1)]
    citation_map = {1: "src_1"}
    blocks = inject_citations(text, citations, citation_map)
    assert len(blocks) == 1
    block = blocks[0]
    assert isinstance(block, BlockParagraph)
    assert block.text == "研究表明该方法有效"
    assert block.citations is not None
    assert len(block.citations) == 1
    assert block.citations[0].sourceId == "src_1"


def test_inject_citations_no_refs():
    text = "普通文本"
    blocks = inject_citations(text, [], {})
    assert len(blocks) == 1
    assert isinstance(blocks[0], BlockParagraph)
    assert blocks[0].text == "普通文本"
    assert blocks[0].citations is None
