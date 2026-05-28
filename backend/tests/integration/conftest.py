"""集成测试共享 fixtures"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# 样本目录
_FIXTURES_DIR = BACKEND_ROOT / "tests" / "fixtures"
ZH_PDF_DIR = _FIXTURES_DIR / "pdfs_zh"
EN_PDF_DIR = _FIXTURES_DIR / "pdfs_en"
OUTPUT_DIR = BACKEND_ROOT / "tests" / "output"


def _find_first_pdf(directory: Path) -> Path | None:
    if not directory.exists():
        return None
    for f in directory.iterdir():
        if f.suffix.lower() == ".pdf":
            return f
    return None


@pytest.fixture
def zh_pdf():
    pdf = _find_first_pdf(ZH_PDF_DIR)
    if pdf is None:
        pytest.skip("中文 PDF 样本不存在")
    return pdf


@pytest.fixture
def en_pdf():
    pdf = _find_first_pdf(EN_PDF_DIR)
    if pdf is None:
        pytest.skip("英文 PDF 样本不存在")
    return pdf


@pytest.fixture
def output_dir():
    import time
    run_id = f"run_{int(time.time())}"
    out = OUTPUT_DIR / "integration" / run_id
    out.mkdir(parents=True, exist_ok=True)
    return out
