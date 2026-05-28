"""MinerU JSON 元数据分析

解析中英文测试论文，保存 JSON 元数据，分析结构。
输出按 zh/ en/ 分目录。

运行: uv run pytest tests/integration/data_layer/test_mineru_json_analysis.py -v -s
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

_TEST_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = _TEST_ROOT / "output" / "mineru_json_analysis"

TOKEN = os.environ.get("MINERU_TOKEN", "")

# ── 中文样本 ──────────────────────────────────────────────
ZH_PAPERS = [
    ("2018", "2018 - 中共中央国务院印发《乡村振兴战略规划(2018—2022年)》.pdf"),
    ("VR", "VR技术在公共文化服务中的应用研究_黄金铭.pdf"),
    ("刘威", "“城乡”作为一个治理单元：城乡共治的理论争辩与中国实践_刘威.pdf"),
    ("谭明方", "“城乡融合发展”视角的县域社会治理研究_谭明方.pdf"),
    ("郜清攀", "乡村振兴战略背景下乡镇政府公共服务能力研究_郜清攀.pdf"),
]

# ── 英文样本（取前3个有代表性的） ──────────────────────────
EN_PAPERS = [
    ("en-1", "1.pdf"),
    ("en-10", "10.pdf"),
    ("en-103", "103.pdf"),
]


def _save_results(tag: str, result, output_dir: Path):
    """保存解析结果到指定目录"""
    tag_dir = output_dir / tag
    tag_dir.mkdir(parents=True, exist_ok=True)

    metadata = result.metadata

    # 保存 markdown
    (tag_dir / "full.md").write_text(result.markdown, encoding="utf-8")

    # 保存 JSON 文件
    for key in ("content_list", "model", "layout"):
        if key in metadata:
            out = tag_dir / f"{key}.json"
            out.write_text(json.dumps(metadata[key], ensure_ascii=False, indent=2), encoding="utf-8")

    # 统计
    cl = metadata.get("content_list", [])
    model = metadata.get("model", [])
    image_count = len(metadata.get("image_paths", []))

    types = {}
    for item in cl:
        t = item.get("type", "unknown")
        types[t] = types.get(t, 0) + 1

    labels = {}
    for page in model:
        for det in page.get("layout_dets", []):
            lb = det.get("label", "unknown")
            labels[lb] = labels.get(lb, 0) + 1

    print(f"\n{'='*60}")
    print(f"[{tag}] {Path(result.metadata.get('file_name', '')).name or tag}")
    print(f"  Markdown: {len(result.markdown):,} chars")
    print(f"  Page count: {result.page_count}")
    print(f"  Images: {image_count}")
    print(f"  Split count: {result.split_count}")
    if cl:
        print(f"  content_list: {len(cl)} 条, types={types}")
    if model:
        print(f"  model: {len(model)} 页, labels={labels}")
    print(f"{'='*60}")


@pytest.fixture(scope="module")
def zh_output():
    d = OUTPUT_DIR / "zh"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture(scope="module")
def en_output():
    d = OUTPUT_DIR / "en"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.mark.asyncio
@pytest.mark.parametrize("tag,filename", ZH_PAPERS)
async def test_zh_pdf(tag, filename, zh_output):
    """中文 PDF 解析"""
    if not TOKEN:
        pytest.skip("需要 MINERU_TOKEN 环境变量")
    import sys
    if str(_TEST_ROOT.parent) not in sys.path:
        sys.path.insert(0, str(_TEST_ROOT.parent))

    from app.data_layer.preprocessing.transformation.mineru_client import MinerUClient

    pdf_path = _TEST_ROOT / "fixtures" / "pdfs_zh" / filename
    if not pdf_path.exists():
        pytest.skip(f"PDF 不存在: {pdf_path}")

    client = MinerUClient(token=TOKEN, max_retries=3)
    result = await client.parse_document(pdf_path)

    if not result.success:
        pytest.fail(f"MinerU 解析失败: {result.error}")

    _save_results(tag, result, zh_output)
    assert len(result.markdown) > 0, f"[{tag}] Markdown 为空"


@pytest.mark.asyncio
@pytest.mark.parametrize("tag,filename", EN_PAPERS)
async def test_en_pdf(tag, filename, en_output):
    """英文 PDF 解析"""
    if not TOKEN:
        pytest.skip("需要 MINERU_TOKEN 环境变量")
    import sys
    if str(_TEST_ROOT.parent) not in sys.path:
        sys.path.insert(0, str(_TEST_ROOT.parent))

    from app.data_layer.preprocessing.transformation.mineru_client import MinerUClient

    pdf_path = _TEST_ROOT / "fixtures" / "pdfs_en" / filename
    if not pdf_path.exists():
        pytest.skip(f"PDF 不存在: {pdf_path}")

    client = MinerUClient(token=TOKEN, max_retries=3)
    result = await client.parse_document(pdf_path)

    if not result.success:
        pytest.fail(f"MinerU 解析失败: {result.error}")

    _save_results(tag, result, en_output)
    assert len(result.markdown) > 0, f"[{tag}] Markdown 为空"
