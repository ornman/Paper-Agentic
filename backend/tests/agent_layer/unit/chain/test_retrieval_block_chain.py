"""retrieval → source_mapper → citation_resolver → block_streamer 完整链路集成测试"""

from __future__ import annotations

import pytest

from app.agent_layer.contracts.content_block import BlockCitation, BlockParagraph
from app.agent_layer.contracts.source_card import SourceCard
from app.agent_layer.response.block_streamer import stream_to_blocks
from app.agent_layer.response.citation_resolver import (
    build_citation_map,
    extract_citations,
    inject_citations,
)
from app.agent_layer.response.source_mapper import map_sources


# ── helpers ──────────────────────────────────────────────────────────


def _make_retrieval_results(n: int) -> list[dict]:
    """生成 n 条模拟检索结果"""
    return [
        {
            "paper_id": f"paper_{i}",
            "chunk_id": f"chunk_{i}",
            "title": f"论文{i}",
            "page": i,
            "section": f"第{i}章",
            "content": f"这是第{i}篇论文的内容摘要，讨论了相关方法和结论。" * 5,
        }
        for i in range(1, n + 1)
    ]


# ── source_mapper ────────────────────────────────────────────────────


async def test_source_mapper_basic():
    """检索结果 → SourceCard 列表"""
    results = _make_retrieval_results(3)
    sources = map_sources(results)
    assert len(sources) == 3
    assert all(isinstance(s, SourceCard) for s in sources)
    # 实际 ID 格式: src_{paper_id}_{chunk_id}
    assert all(s.id.startswith("src_") for s in sources)


async def test_source_mapper_id_uniqueness():
    """不同结果生成不同 id"""
    results = _make_retrieval_results(10)
    sources = map_sources(results)
    ids = [s.id for s in sources]
    assert len(ids) == len(set(ids))


async def test_source_mapper_content_truncate():
    """超长内容被截断到 220 字符 + 省略号"""
    results = [
        {
            "paper_id": "p1",
            "chunk_id": "c1",
            "title": "t",
            "page": 1,
            "section": "s",
            "content": "x" * 500,
        }
    ]
    sources = map_sources(results)
    # 220 字符 + "…" = 221
    assert len(sources[0].content) == 221
    assert sources[0].content.endswith("…")


async def test_source_mapper_short_content_unchanged():
    """短内容不截断"""
    results = [
        {
            "paper_id": "p1",
            "chunk_id": "c1",
            "title": "t",
            "page": 1,
            "section": "s",
            "content": "短文本",
        }
    ]
    sources = map_sources(results)
    assert sources[0].content == "短文本"


async def test_source_mapper_empty_input():
    """空输入 → 空列表"""
    sources = map_sources([])
    assert sources == []


async def test_source_mapper_preserves_metadata():
    """保留 paper_id, title, page, section 等元数据"""
    results = _make_retrieval_results(1)
    sources = map_sources(results)
    s = sources[0]
    assert s.paper_id == "paper_1"
    assert s.title == "论文1"
    assert s.page == 1
    assert s.section == "第1章"


# ── citation_resolver ────────────────────────────────────────────────


async def test_citation_extraction():
    """提取 [1][2][3] 引用标记"""
    text = "研究表明[1]该方法有效[2][3]，优于基线[1]。"
    citations = extract_citations(text)
    indices = [c[2] for c in citations]
    assert 1 in indices
    assert 2 in indices
    assert 3 in indices


async def test_citation_extraction_no_citations():
    """无引用标记 → 空列表"""
    citations = extract_citations("这是一段普通文本。")
    assert citations == []


async def test_citation_to_source_mapping():
    """引用索引 → SourceCard.id 映射"""
    results = _make_retrieval_results(3)
    sources = map_sources(results)
    text = "根据研究[1][3]的结论..."
    citations = extract_citations(text)
    mapping = build_citation_map(citations, sources)
    assert mapping[1] == sources[0].id
    assert mapping[3] == sources[2].id


async def test_citation_out_of_range_ignored():
    """超出 sources 范围的引用索引被忽略"""
    results = _make_retrieval_results(2)
    sources = map_sources(results)
    citations = extract_citations("引用[1]和[5]。")
    mapping = build_citation_map(citations, sources)
    assert 1 in mapping
    assert 5 not in mapping


async def test_inject_citations_basic():
    """inject_citations 正确插入 BlockCitation"""
    text = "研究表明[1]该方法有效。"
    citations = extract_citations(text)
    results = _make_retrieval_results(1)
    sources = map_sources(results)
    citation_map = build_citation_map(citations, sources)
    blocks = inject_citations(text, citations, citation_map)
    assert len(blocks) == 1
    paragraph = blocks[0]
    assert isinstance(paragraph, BlockParagraph)
    assert paragraph.citations is not None
    assert len(paragraph.citations) == 1
    assert paragraph.citations[0].sourceId == sources[0].id
    # 原始文本中的 [1] 应被移除
    assert "[1]" not in paragraph.text


# ── block_streamer 完整链路 ─────────────────────────────────────────


async def test_full_chain_retrieval_to_blocks():
    """完整链路：检索结果 → SourceCard → 带引用的 ContentBlock"""
    results = _make_retrieval_results(3)
    sources = map_sources(results)
    llm_output = "研究表明[1]该方法在多个数据集上有效[2]，显著优于基线[3]。"
    blocks = stream_to_blocks(llm_output, sources)
    assert len(blocks) > 0
    paragraph = blocks[0]
    assert isinstance(paragraph, BlockParagraph)
    assert paragraph.citations is not None
    assert len(paragraph.citations) > 0


async def test_chain_with_no_citations():
    """LLM 输出无引用 → 纯文本 BlockParagraph"""
    sources = map_sources(_make_retrieval_results(3))
    blocks = stream_to_blocks("这是一段普通文本，没有引用。", sources)
    assert len(blocks) == 1
    assert isinstance(blocks[0], BlockParagraph)
    assert blocks[0].citations is None or len(blocks[0].citations) == 0


async def test_chain_with_empty_retrieval():
    """空检索结果 → sources 为空，blocks 只有文本"""
    sources = map_sources([])
    blocks = stream_to_blocks("没有检索结果的回答。", sources)
    assert len(blocks) >= 1
    assert all(isinstance(b, BlockParagraph) for b in blocks)


async def test_chain_multiline_with_citations():
    """多行输出混合引用"""
    results = _make_retrieval_results(3)
    sources = map_sources(results)
    llm_output = "第一段引用[1]。\n\n第二段引用[2][3]。"
    blocks = stream_to_blocks(llm_output, sources)
    assert len(blocks) >= 2
    # 两个段落都有引用
    for block in blocks:
        assert isinstance(block, BlockParagraph)


async def test_chain_heading_and_paragraph():
    """标题 + 段落混合"""
    sources = map_sources(_make_retrieval_results(1))
    llm_output = "## 结论\n研究表明[1]该方法有效。"
    blocks = stream_to_blocks(llm_output, sources)
    assert len(blocks) == 2
    from app.agent_layer.contracts.content_block import BlockHeading

    assert isinstance(blocks[0], BlockHeading)
    assert blocks[0].text == "结论"
    assert isinstance(blocks[1], BlockParagraph)
