"""MinerU 批量 PDF 解析脚本

将 datasets/ 下的 PDF 批量提交到 MinerU 精准解析 API，
下载 Markdown 结果到 Original_data_Markdown/，不做任何清洗。

用法: python batch_parse.py [--dry-run] [--resume]
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import random
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

import requests

# ── 配置 ──────────────────────────────────────────────────────────────

TOKEN = "eyJ0eXBlIjoiSldUIiwiYWxnIjoiSFM1MTIifQ.eyJqdGkiOiI0NDIwMDY2OCIsInJvbCI6IlJPTEVfUkVHSVNURVIiLCJpc3MiOiJPcGVuWExhYiIsImlhdCI6MTc3OTgwMDUwNCwiY2xpZW50SWQiOiJsa3pkeDU3bnZ5MjJqa3BxOXgydyIsInBob25lIjoiIiwib3BlbklkIjpudWxsLCJ1dWlkIjoiZGI2MTc1ZWQtNTg3My00NjllLWI1ZGItMTI5MGYxMDBiNWUyIiwiZW1haWwiOiIyODI2ODI5ODc3QHFxLmNvbSIsImV4cCI6MTc4NzU3NjUwNH0.EGB0oIVwJOGYSAFfI2y_sS-_dh-Eynuxogyz8tCY2vTQbeTF3kusjFCjLoVWEDzNegSz8WXdvNb4j5VNW8qg_A"

BASE_URL = "https://mineru.net/api/v4"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}",
}

BATCH_SIZE = 50           # 单次最多 50 个文件
POLL_INTERVAL = 5         # 轮询间隔（秒）
MAX_RETRIES = 3           # 最大重试次数
RETRY_BASE_DELAY = 45     # 重试基础间隔（秒）
MAX_CONCURRENT_UPLOADS = 10  # 并发上传数
POLL_TIMEOUT = 600        # 单个任务轮询超时（秒）

# 路径
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
PDF_DIRS = [
    PROJECT_ROOT / "datasets" / "外文文献-测试-PDF",
    PROJECT_ROOT / "datasets" / "中文文献-测试-PDF",
]
OUTPUT_DIR = SCRIPT_DIR / "Original_data_Markdown"
PROGRESS_FILE = SCRIPT_DIR / ".batch_progress.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("mineru-batch")


# ── 数据结构 ──────────────────────────────────────────────────────────

@dataclass
class PdfTask:
    pdf_path: Path
    rel_key: str          # 唯一标识（用于输出文件名和进度追踪）
    language: str = "ch"
    retries: int = 0
    status: str = "pending"  # pending / uploading / submitted / done / failed
    task_id: str = ""
    batch_id: str = ""
    error: str = ""


@dataclass
class BatchState:
    """断点续传状态"""
    completed: dict[str, str] = field(default_factory=dict)  # rel_key -> md_path
    failed: dict[str, str] = field(default_factory=dict)      # rel_key -> error


# ── 工具函数 ──────────────────────────────────────────────────────────

def retry_delay() -> float:
    """45s 基础 + 随机抖动 ±15s"""
    return RETRY_BASE_DELAY + random.uniform(-15, 15)


def flatten_rel_key(pdf_path: Path) -> str:
    """用 PDF 文件名作为 key，重名时加目录前缀区分"""
    return pdf_path.stem


def _resolve_collision(tasks: list[PdfTask]) -> None:
    """检测并解决 rel_key 重名：加父目录名前缀"""
    from collections import Counter
    counts = Counter(t.rel_key for t in tasks)
    dupes = {k for k, v in counts.items() if v > 1}
    for t in tasks:
        if t.rel_key in dupes:
            t.rel_key = f"{t.pdf_path.parent.name}_{t.rel_key}"


def collect_pdfs() -> list[PdfTask]:
    """收集所有 PDF 文件"""
    tasks = []
    for pdf_dir in PDF_DIRS:
        if not pdf_dir.exists():
            logger.warning("目录不存在: %s", pdf_dir)
            continue
        # 确定语言
        if "外文" in pdf_dir.name:
            lang = "en"
        else:
            lang = "ch"
        for pdf in sorted(pdf_dir.rglob("*.pdf")):
            key = flatten_rel_key(pdf)
            tasks.append(PdfTask(pdf_path=pdf, rel_key=key, language=lang))
    return tasks


def load_progress() -> BatchState:
    """加载断点续传状态"""
    if PROGRESS_FILE.exists():
        data = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        return BatchState(
            completed=data.get("completed", {}),
            failed=data.get("failed", {}),
        )
    return BatchState()


def save_progress(state: BatchState) -> None:
    """保存进度"""
    PROGRESS_FILE.write_text(
        json.dumps({"completed": state.completed, "failed": state.failed},
                    ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── MinerU API 调用 ──────────────────────────────────────────────────

def get_upload_urls(file_names: list[str], language: str = "ch") -> dict:
    """申请批量上传链接

    Returns:
        {"batch_id": str, "urls": [(file_name, upload_url), ...]}
    """
    # data_id 限 128 字节，长文件名用 hash 截断
    import hashlib
    def _safe_data_id(name: str) -> str:
        if len(name.encode("utf-8")) <= 120:
            return name
        # 按字节截断到 110，加 8 字符 hash
        raw = name.encode("utf-8")[:110]
        # 确保不截断多字节字符中间
        truncated = raw.decode("utf-8", errors="ignore")
        return truncated + "_" + hashlib.md5(name.encode()).hexdigest()[:8]

    payload = {
        "files": [{"name": name, "data_id": _safe_data_id(name)} for name in file_names],
        "enable_formula": True,
        "enable_table": True,
        "language": language,
    }
    resp = requests.post(
        f"{BASE_URL}/file-urls/batch",
        headers=HEADERS,
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()
    if result.get("code") != 0:
        raise RuntimeError(f"获取上传链接失败: {result}")

    data = result["data"]
    batch_id = data["batch_id"]
    url_list = data.get("file_urls", [])
    # 按顺序配对: file_names[i] ↔ url_list[i]
    urls = list(zip(file_names, url_list))
    return {"batch_id": batch_id, "urls": urls}


def upload_file(upload_url: str, pdf_path: Path) -> None:
    """上传单个文件到预签名 URL"""
    with open(pdf_path, "rb") as f:
        resp = requests.put(upload_url, data=f, timeout=120)
        resp.raise_for_status()


def poll_batch_result(batch_id: str) -> dict:
    """轮询批量任务结果"""
    start = time.monotonic()
    network_errors = 0
    while time.monotonic() - start < POLL_TIMEOUT:
        try:
            resp = requests.get(
                f"{BASE_URL}/extract-results/batch/{batch_id}",
                headers=HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            network_errors = 0
        except (requests.ConnectionError, requests.Timeout) as e:
            network_errors += 1
            if network_errors >= 5:
                raise TimeoutError(f"批次 {batch_id} 网络连续失败 {network_errors} 次") from e
            logger.warning("轮询网络错误 (%d/5): %s", network_errors, e)
            time.sleep(POLL_INTERVAL)
            continue
        result = resp.json()
        if result.get("code") != 0:
            logger.warning("轮询返回异常: %s", result)
            time.sleep(POLL_INTERVAL)
            continue

        data = result.get("data", {})
        # 检查是否全部完成
        extract_result = data.get("extract_result", [])
        if not extract_result:
            time.sleep(POLL_INTERVAL)
            continue

        all_done = all(
            item.get("state") in ("done", "failed")
            for item in extract_result
        )
        if all_done:
            return data

        # 打印进度
        done_count = sum(1 for item in extract_result if item.get("state") == "done")
        failed_count = sum(1 for item in extract_result if item.get("state") == "failed")
        running_count = len(extract_result) - done_count - failed_count
        logger.info(
            "  批次 %s: 完成=%d, 失败=%d, 进行中=%d",
            batch_id[:8], done_count, failed_count, running_count,
        )
        time.sleep(POLL_INTERVAL)

    raise TimeoutError(f"批次 {batch_id} 轮询超时 ({POLL_TIMEOUT}s)")


def download_and_extract_md(zip_url: str) -> str:
    """下载 zip 并提取 full.md"""
    resp = requests.get(zip_url, timeout=120)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        # 找 full.md
        for name in zf.namelist():
            if name.endswith("full.md"):
                return zf.read(name).decode("utf-8")
        # 如果没有 full.md，找任意 .md
        for name in zf.namelist():
            if name.endswith(".md"):
                return zf.read(name).decode("utf-8")
    raise RuntimeError("zip 中未找到 .md 文件")


# ── 主流程 ────────────────────────────────────────────────────────────

def process_batch(
    batch_tasks: list[PdfTask],
    state: BatchState,
    attempt: int = 1,
) -> None:
    """处理一个批次（最多 50 个文件）"""

    # 按语言分组（API 要求同批次语言一致）
    by_lang: dict[str, list[PdfTask]] = {}
    for t in batch_tasks:
        by_lang.setdefault(t.language, []).append(t)

    for lang, tasks in by_lang.items():
        if not tasks:
            continue

        logger.info("批次语言=%s, 文件数=%d, 第 %d 次尝试", lang, len(tasks), attempt)

        # 1. 申请上传链接
        file_names = [t.pdf_path.name for t in tasks]
        try:
            url_data = get_upload_urls(file_names, language=lang)
        except Exception as e:
            logger.error("获取上传链接失败: %s", e)
            for t in tasks:
                t.status = "failed"
                t.error = str(e)
            return

        batch_id = url_data["batch_id"]
        url_pairs = url_data["urls"]  # [(file_name, upload_url), ...]

        if not url_pairs:
            logger.error("响应中无上传链接")
            for t in tasks:
                t.status = "failed"
                t.error = "无上传链接"
            return

        # 2. 并发上传
        logger.info("开始上传 %d 个文件...", len(tasks))
        upload_map: dict[str, str] = dict(url_pairs)

        def _upload_task(task: PdfTask) -> tuple[PdfTask, bool]:
            url = upload_map.get(task.pdf_path.name)
            if not url:
                logger.warning("未找到上传链接: %s", task.pdf_path.name)
                return task, False
            try:
                upload_file(url, task.pdf_path)
                task.status = "submitted"
                return task, True
            except Exception as e:
                logger.warning("上传失败 %s: %s", task.pdf_path.name, e)
                task.error = str(e)
                return task, False

        failed_uploads: list[PdfTask] = []
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_UPLOADS) as pool:
            futures = {pool.submit(_upload_task, t): t for t in tasks}
            for future in as_completed(futures):
                task, ok = future.result()
                if not ok:
                    failed_uploads.append(task)

        if failed_uploads:
            logger.warning("上传失败 %d 个文件", len(failed_uploads))

        logger.info("批量任务已提交, batch_id=%s, 开始轮询...", batch_id[:8])

        # 4. 轮询结果
        try:
            result_data = poll_batch_result(batch_id)
        except TimeoutError as e:
            logger.error("轮询超时: %s", e)
            for t in tasks:
                if t.status == "submitted":
                    t.status = "failed"
                    t.error = str(e)
            return

        # 5. 下载并保存 Markdown
        extract_results = result_data.get("extract_result", [])
        result_map: dict[str, dict] = {}
        for item in extract_results:
            result_map[item.get("data_id", "")] = item

        # 构建 name → data_id 映射（data_id 可能被截断）
        import hashlib
        def _safe_data_id(name: str) -> str:
            if len(name.encode("utf-8")) <= 120:
                return name
            raw = name.encode("utf-8")[:110]
            truncated = raw.decode("utf-8", errors="ignore")
            return truncated + "_" + hashlib.md5(name.encode()).hexdigest()[:8]

        for task in tasks:
            item = result_map.get(task.pdf_path.name) or result_map.get(_safe_data_id(task.pdf_path.name))
            if not item:
                task.status = "failed"
                task.error = "结果中未找到该文件"
                continue

            if item.get("state") == "done":
                zip_url = item.get("full_zip_url", "")
                if not zip_url:
                    task.status = "failed"
                    task.error = "done 但无 zip_url"
                    continue
                try:
                    md_text = download_and_extract_md(zip_url)
                    out_path = OUTPUT_DIR / f"{task.rel_key}.md"
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_text(md_text, encoding="utf-8")
                    task.status = "done"
                    state.completed[task.rel_key] = str(out_path)
                    logger.info("  ✓ %s", task.rel_key)
                except Exception as e:
                    task.status = "failed"
                    task.error = str(e)
                    logger.warning("  ✗ %s: %s", task.rel_key, e)
            else:
                task.status = "failed"
                task.error = item.get("err_msg", f"state={item.get('state')}")
                logger.warning("  ✗ %s: %s", task.rel_key, task.error)

    # 更新失败记录
    for t in batch_tasks:
        if t.status == "failed":
            state.failed[t.rel_key] = t.error


def main():
    parser = argparse.ArgumentParser(description="MinerU 批量 PDF 解析")
    parser.add_argument("--dry-run", action="store_true", help="只列出文件，不执行")
    parser.add_argument("--resume", action="store_true", help="断点续传，跳过已完成")
    args = parser.parse_args()

    # 收集 PDF
    all_tasks = collect_pdfs()
    _resolve_collision(all_tasks)
    logger.info("共发现 %d 个 PDF 文件", len(all_tasks))

    if args.dry_run:
        for t in all_tasks:
            print(f"  {t.rel_key}  [{t.language}]  {t.pdf_path}")
        return

    # 加载进度
    state = load_progress()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 过滤已完成
    if args.resume:
        pending = [t for t in all_tasks if t.rel_key not in state.completed]
        logger.info("断点续传: 已完成 %d, 待处理 %d", len(state.completed), len(pending))
    else:
        pending = all_tasks
        state = BatchState()

    if not pending:
        logger.info("所有文件已处理完毕")
        return

    # 分批处理（每批最多 BATCH_SIZE 个）
    total = len(pending)
    done_count = 0
    failed_count = 0

    for i in range(0, total, BATCH_SIZE):
        batch = pending[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        logger.info(
            "═══ 批次 %d/%d (文件 %d-%d) ═══",
            batch_num, total_batches, i + 1, min(i + BATCH_SIZE, total),
        )

        # 带重试的批次处理
        for attempt in range(1, MAX_RETRIES + 1):
            # 标记待重试的文件
            retry_batch = [t for t in batch if t.status in ("pending", "failed")]
            if not retry_batch:
                break

            if attempt > 1:
                delay = retry_delay()
                logger.info("等待 %.1fs 后重试 (第 %d/%d 次)...", delay, attempt, MAX_RETRIES)
                time.sleep(delay)

            process_batch(retry_batch, state, attempt)

            # 检查哪些还需要重试
            still_failed = [t for t in retry_batch if t.status == "failed"]
            if not still_failed:
                break
            logger.warning("批次 %d: %d 个文件仍然失败", batch_num, len(still_failed))

        # 统计本批次结果
        for t in batch:
            if t.status == "done":
                done_count += 1
            elif t.status == "failed":
                failed_count += 1
                state.failed[t.rel_key] = t.error

        # 保存进度
        save_progress(state)
        logger.info("进度: 完成=%d, 失败=%d, 剩余=%d", done_count, failed_count, total - done_count - failed_count)

    # 最终报告
    logger.info("═══ 处理完成 ═══")
    logger.info("总计: %d, 成功: %d, 失败: %d", total, done_count, failed_count)
    if state.failed:
        logger.info("失败文件列表:")
        for key, err in state.failed.items():
            logger.info("  ✗ %s: %s", key, err[:80])

    save_progress(state)


if __name__ == "__main__":
    main()
