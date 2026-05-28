"""MinerU vs MarkItDown 对比测试

用 MinerU Agent API（免费）重新解析 5 篇测试论文，
对比 MarkItDown 的转换质量。

运行: uv run pytest tests/data_layer/test_mineru_comparison.py -v -s
"""

from __future__ import annotations

import json
import os
import re
import time
import zipfile
import io
import pytest
import requests
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────────
MINERU_AGENT_BASE = "https://mineru.net/api/v1/agent"
MINERU_V4_BASE = "https://mineru.net/api/v4"
MINERU_TOKEN = os.environ.get("MINERU_TOKEN", "")

_TEST_ROOT = Path(__file__).resolve().parents[2]  # backend/tests
PDF_DIR = _TEST_ROOT / "fixtures" / "pdfs_zh"
MARKDOWN_DIR = _TEST_ROOT / "_legacy" / "data_UnitTest"
OUTPUT_DIR = _TEST_ROOT / "output" / "mineru_comparison"

# 5 篇测试论文
TEST_PAPERS = [
    ("2018", "2018 - 中共中央国务院印发《乡村振兴战略规划(2018—2022年)》.pdf"),
    ("VR", "VR技术在公共文化服务中的应用研究_黄金铭.pdf"),
    ("刘威", "\"城乡\"作为一个治理单元：城乡共治的理论争辩与中国实践_刘威.pdf"),
    ("谭明方", "\"城乡融合发展\"视角的县域社会治理研究_谭明方.pdf"),
    ("郜清攀", "乡村振兴战略背景下乡镇政府公共服务能力研究_郜清攀.pdf"),
]


def _find_pdf(fragment: str) -> Path | None:
    """在 PDF 目录中查找匹配的文件（支持模糊匹配）"""
    for f in PDF_DIR.iterdir():
        if f.suffix.lower() == ".pdf" and fragment in f.name:
            return f
    # 模糊匹配：用 fragment 中的中文部分搜索
    clean = re.sub(r'[^一-鿿]', '', fragment)
    if clean:
        for f in PDF_DIR.iterdir():
            if f.suffix.lower() == ".pdf" and clean in f.name:
                return f
    return None


def _submit_to_mineru_v4(pdf_path: Path, page_ranges: str | None = None) -> str:
    """用精准解析 API 提交 PDF（需 Token）

    Returns: task_id
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MINERU_TOKEN}",
    }

    # 精准 API 需要 URL，先用 batch 上传接口
    # 申请上传链接
    files_payload = {
        "files": [{"name": pdf_path.name}],
        "model_version": "pipeline",
        "enable_table": True,
        "language": "ch",
    }
    if page_ranges:
        files_payload["files"][0]["page_ranges"] = page_ranges

    resp = requests.post(
        f"{MINERU_V4_BASE}/file-urls/batch",
        headers=headers,
        json=files_payload,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("code") != 0:
        raise Exception(f"申请上传链接失败: {data}")

    batch_id = data["data"]["batch_id"]
    file_urls = data["data"]["file_urls"]

    if not file_urls:
        raise Exception("未获取到上传链接")

    # 上传文件
    with open(pdf_path, "rb") as f:
        upload_resp = requests.put(file_urls[0], data=f, timeout=120)
        upload_resp.raise_for_status()

    return batch_id


def _poll_mineru_v4_batch(batch_id: str, timeout: int = 300) -> list[dict]:
    """轮询精准 API 批量结果"""
    headers = {"Authorization": f"Bearer {MINERU_TOKEN}"}
    start = time.time()

    while time.time() - start < timeout:
        resp = requests.get(
            f"{MINERU_V4_BASE}/extract-results/batch/{batch_id}",
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise Exception(f"查询失败: {data}")

        results = data["data"].get("extract_result", [])
        all_done = all(
            r.get("state") in ("done", "failed")
            for r in results
        )

        if all_done:
            return results

        # 显示进度
        for r in results:
            state = r.get("state")
            progress = r.get("extract_progress", {})
            if state == "running" and progress:
                print(f"  进度: {progress.get('extracted_pages', 0)}/{progress.get('total_pages', '?')} 页", end="\r")

        time.sleep(5)

    raise TimeoutError(f"超时 ({timeout}s)")


def _download_markdown(zip_url: str) -> str:
    """从 Zip 包中提取 full.md"""
    resp = requests.get(zip_url, timeout=60)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        # 找 full.md
        for name in zf.namelist():
            if name.endswith("full.md"):
                return zf.read(name).decode("utf-8")

        # 如果没有 full.md，找任何 .md 文件
        for name in zf.namelist():
            if name.endswith(".md"):
                return zf.read(name).decode("utf-8")

    raise Exception("Zip 包中未找到 Markdown 文件")


def _analyze_quality(text: str, keywords: list[str]) -> dict:
    """分析文本质量"""
    lines = text.split("\n")
    non_empty = [l for l in lines if l.strip()]
    table_lines = sum(1 for l in lines if l.strip().startswith("|"))
    pua_count = len(re.findall(r"[-]", text))

    # 行长分布
    lengths = [len(l.strip()) for l in non_empty]
    avg_len = sum(lengths) / max(len(lengths), 1)
    short_lines = sum(1 for l in lengths if l <= 5)

    # 关键词计数
    kw_counts = {kw: text.count(kw) for kw in keywords}

    return {
        "total_chars": len(text),
        "total_lines": len(lines),
        "non_empty_lines": len(non_empty),
        "table_lines": table_lines,
        "pua_chars": pua_count,
        "avg_line_length": round(avg_len, 1),
        "short_lines_pct": round(short_lines / max(len(lengths), 1) * 100, 1),
        "keyword_counts": kw_counts,
    }


# ── 测试类 ────────────────────────────────────────────────

@pytest.mark.skipif(
    not PDF_DIR.exists(),
    reason="PDF 测试样本不存在",
)
class TestMinerUComparison:
    """MinerU vs MarkItDown 对比测试"""

    def test_mineru_parse_all_5_papers(self, tmp_path):
        """用 MinerU 精准 API 解析 5 篇论文并对比"""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        keywords_map = {
            "2018": ["乡村振兴", "中共中央", "国务院", "三农"],
            "VR": ["VR", "虚拟现实", "博物馆", "沉浸", "交互"],
            "刘威": ["城乡融合", "治理单元", "社会共生", "粘连状态"],
            "谭明方": ["县域", "社会治理", "城乡融合", "城乡政治"],
            "郜清攀": ["乡村振兴", "乡镇政府", "公共服务", "治理现代化"],
        }

        report_lines = []
        report_lines.append("=" * 90)
        report_lines.append("MinerU vs MarkItDown 质量对比报告")
        report_lines.append("=" * 90)

        for tag, pdf_name in TEST_PAPERS:
            # 先用 tag 搜索，再用文件名搜索
            pdf_path = _find_pdf(tag)
            if pdf_path is None:
                pdf_path = _find_pdf(pdf_name.replace(".pdf", ""))
            if pdf_path is None:
                report_lines.append(f"\n【{tag}】PDF 未找到，跳过")
                continue

            report_lines.append(f"\n{'─'*80}")
            report_lines.append(f"【{tag}】{pdf_path.name}")
            report_lines.append(f"{'─'*80}")

            # 1. 读取 MarkItDown 输出
            md_dir = None
            for d in MARKDOWN_DIR.iterdir():
                if tag in d.name:
                    md_dir = d
                    break

            if md_dir and (md_dir / "converted.md").exists():
                markitdown_text = (md_dir / "converted.md").read_text(encoding="utf-8")
                md_quality = _analyze_quality(markitdown_text, keywords_map.get(tag, []))
                report_lines.append(f"\n  MarkItDown:")
                report_lines.append(f"    字符数: {md_quality['total_chars']}")
                report_lines.append(f"    总行数: {md_quality['total_lines']}")
                report_lines.append(f"    非空行: {md_quality['non_empty_lines']}")
                report_lines.append(f"    表格行: {md_quality['table_lines']} ({md_quality['table_lines']*100//max(md_quality['non_empty_lines'],1)}%)")
                report_lines.append(f"    PUA 字符: {md_quality['pua_chars']}")
                report_lines.append(f"    平均行长: {md_quality['avg_line_length']}")
                report_lines.append(f"    短行比例: {md_quality['short_lines_pct']}%")
                report_lines.append(f"    关键词: {md_quality['keyword_counts']}")
            else:
                report_lines.append(f"\n  MarkItDown: 未找到 converted.md")

            # 2. 用 MinerU 解析
            report_lines.append(f"\n  MinerU: 提交中...")

            try:
                # 用精准 API，先试前 20 页（Agent API 限制）
                batch_id = _submit_to_mineru_v4(pdf_path, page_ranges="1-20")
                results = _poll_mineru_v4_batch(batch_id, timeout=300)

                if results and results[0].get("state") == "done":
                    zip_url = results[0].get("full_zip_url")
                    if zip_url:
                        mineru_text = _download_markdown(zip_url)

                        # 保存 MinerU 输出
                        output_file = OUTPUT_DIR / f"{tag}_mineru.md"
                        output_file.write_text(mineru_text, encoding="utf-8")

                        mu_quality = _analyze_quality(mineru_text, keywords_map.get(tag, []))
                        report_lines.append(f"  MinerU (前20页):")
                        report_lines.append(f"    字符数: {mu_quality['total_chars']}")
                        report_lines.append(f"    总行数: {mu_quality['total_lines']}")
                        report_lines.append(f"    非空行: {mu_quality['non_empty_lines']}")
                        report_lines.append(f"    表格行: {mu_quality['table_lines']} ({mu_quality['table_lines']*100//max(mu_quality['non_empty_lines'],1)}%)")
                        report_lines.append(f"    PUA 字符: {mu_quality['pua_chars']}")
                        report_lines.append(f"    平均行长: {mu_quality['avg_line_length']}")
                        report_lines.append(f"    短行比例: {mu_quality['short_lines_pct']}%")
                        report_lines.append(f"    关键词: {mu_quality['keyword_counts']}")

                        # 3. 对比
                        if md_dir and (md_dir / "converted.md").exists():
                            report_lines.append(f"\n  对比:")
                            md_lines = md_quality['non_empty_lines']
                            mu_lines = mu_quality['non_empty_lines']
                            report_lines.append(f"    行数比: MarkItDown {md_lines} vs MinerU {mu_lines}")
                            report_lines.append(f"    表格行: MarkItDown {md_quality['table_lines']} vs MinerU {mu_quality['table_lines']}")
                            report_lines.append(f"    PUA: MarkItDown {md_quality['pua_chars']} vs MinerU {mu_quality['pua_chars']}")

                            # 质量评分
                            md_score = _score_quality(md_quality)
                            mu_score = _score_quality(mu_quality)
                            report_lines.append(f"    质量评分: MarkItDown {md_score}/100 vs MinerU {mu_score}/100")
                    else:
                        report_lines.append(f"  MinerU: 无下载链接")
                elif results and results[0].get("state") == "failed":
                    err = results[0].get("err_msg", "未知错误")
                    report_lines.append(f"  MinerU 失败: {err}")
                else:
                    report_lines.append(f"  MinerU: 状态异常")

            except Exception as e:
                report_lines.append(f"  MinerU 错误: {e}")

        # 输出报告
        report_text = "\n".join(report_lines)
        report_file = OUTPUT_DIR / "comparison_report.txt"
        report_file.write_text(report_text, encoding="utf-8")

        print(f"\n{report_text}")
        print(f"\n报告已保存: {report_file}")


def _score_quality(quality: dict) -> int:
    """质量评分（0-100）"""
    score = 100

    # PUA 字符扣分
    if quality["pua_chars"] > 0:
        score -= min(30, quality["pua_chars"] // 100)

    # 表格行比例扣分（超过 20% 扣分）
    table_pct = quality["table_lines"] / max(quality["non_empty_lines"], 1) * 100
    if table_pct > 50:
        score -= 30
    elif table_pct > 20:
        score -= 15

    # 短行比例扣分（超过 30% 扣分）
    if quality["short_lines_pct"] > 50:
        score -= 20
    elif quality["short_lines_pct"] > 30:
        score -= 10

    # 平均行长过短扣分
    if quality["avg_line_length"] < 10:
        score -= 20
    elif quality["avg_line_length"] < 20:
        score -= 10

    return max(0, score)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
