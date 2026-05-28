"""data_layer 单元测试共享 fixtures"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# 样本目录
_FIXTURES_DIR = BACKEND_ROOT / "tests" / "fixtures"
ZH_PDF_DIR = _FIXTURES_DIR / "pdfs_zh"
EN_PDF_DIR = _FIXTURES_DIR / "pdfs_en"


def _find_first_pdf(directory: Path) -> Path | None:
    """在目录中找到第一个 PDF 文件"""
    if not directory.exists():
        return None
    for f in directory.iterdir():
        if f.suffix.lower() == ".pdf":
            return f
    return None


@pytest.fixture
def tmp_dir():
    """临时目录 fixture

    Windows 上 ChromaDB PersistentClient 可能不释放 SQLite 文件句柄，
    使用 ignore_cleanup_errors=True 避免 teardown 报错。
    """
    import gc
    with tempfile.TemporaryDirectory(prefix="test_data_layer_", ignore_cleanup_errors=True) as d:
        yield Path(d)
    gc.collect()


@pytest.fixture
def zh_pdf():
    """中文 PDF 样本"""
    pdf = _find_first_pdf(ZH_PDF_DIR)
    if pdf is None:
        pytest.skip("中文 PDF 样本不存在")
    return pdf


@pytest.fixture
def en_pdf():
    """英文 PDF 样本"""
    pdf = _find_first_pdf(EN_PDF_DIR)
    if pdf is None:
        pytest.skip("英文 PDF 样本不存在")
    return pdf


@pytest.fixture
def output_dir():
    """测试产出目录（写入 tests/data/）"""
    import time
    run_id = f"run_{int(time.time())}"
    out = BACKEND_ROOT / "tests" / "data" / "data_layer" / run_id
    out.mkdir(parents=True, exist_ok=True)
    return out
