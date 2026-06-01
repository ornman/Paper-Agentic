from __future__ import annotations

from app.agent_layer.response.source_mapper import map_sources


def test_map_sources_normal():
    results = [
        {"paper_id": "p1", "chunk_id": "c1", "title": "论文A", "page": 1, "section": "摘要", "content": "内容一"},
        {"paper_id": "p2", "chunk_id": "c2", "title": "论文B", "page": 5, "section": "方法", "content": "内容二"},
    ]
    cards = map_sources(results)
    assert len(cards) == 2
    assert cards[0].id == "src_p1_c1"
    assert cards[0].paper_id == "p1"
    assert cards[0].title == "论文A"
    assert cards[0].page == 1
    assert cards[0].section == "摘要"
    assert cards[0].content == "内容一"
    assert cards[1].id == "src_p2_c2"


def test_map_sources_empty():
    assert map_sources([]) == []


def test_map_sources_content_truncate():
    long_content = "a" * 300
    results = [{"paper_id": "p1", "chunk_id": "c1", "title": "T", "content": long_content}]
    cards = map_sources(results)
    assert cards[0].content is not None
    assert len(cards[0].content) == 221
    assert cards[0].content.endswith("…")


def test_map_sources_id_uniqueness():
    results = [
        {"paper_id": "p1", "chunk_id": "c1", "title": "T1"},
        {"paper_id": "p1", "chunk_id": "c1", "title": "T2"},
    ]
    cards = map_sources(results)
    assert cards[0].id != cards[1].id


def test_map_sources_missing_fields():
    results = [{"paper_id": "p1"}]
    cards = map_sources(results)
    assert len(cards) == 1
    assert cards[0].title == "未命名论文"
    assert cards[0].content is None
