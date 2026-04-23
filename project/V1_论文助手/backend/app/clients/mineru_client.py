"""MinerU PDF 解析客户端（全异步）"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import random
import zipfile
from dataclasses import dataclass
from time import monotonic
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.utils import error_handler
from app.utils.rate_limiter import RateLimiter

logger = logging.getLogger("paper-assistant")

_SUCCESS_STATES = {"success", "succeeded", "completed", "done"}
_FAILED_STATES = {"failed", "error", "cancelled", "canceled"}
_ALLOWED_CDN_HOSTS = {"cdn-mineru.openxlab.org.cn"}


@dataclass
class MinerUTaskResult:
    task_id: str
    pages: list[dict]  # [{"page": idx, "blocks": [...]}]
    paper_dir: str  # 本地存储目录
    md_content: str | None = None  # Markdown 全文


class MinerUClient:
    def __init__(self):
        settings = get_settings()
        self._base_url = settings.mineru_base_url
        self._api_key = settings.mineru_api_key
        self._poll_interval = settings.mineru_poll_interval
        self._timeout = settings.mineru_timeout
        self._client: httpx.AsyncClient | None = None
        # 提交限速：50/min ≈ 0.83/s（burst 5 允许短时突发）
        self._submit_limiter = RateLimiter(rate=0.83, burst=5)
        # 轮询限速：1000/min ≈ 16.7/s（burst 50）
        self._poll_limiter = RateLimiter(rate=16.7, burst=50)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=60)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _headers(self, auth: bool = True) -> dict[str, str]:
        h: dict[str, str] = {"Accept": "application/json"}
        if auth:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    _SUBMIT_RETRIES = 3

    # --- 提交 ---

    async def submit_task(self, file_path: str) -> str:
        """上传 PDF 并返回 task_id（智能重试）"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF 不存在: {file_path}")

        client = await self._get_client()
        filename = os.path.basename(file_path)
        stem = os.path.splitext(filename)[0]
        # MinerU data_id 限制 128 字节（UTF-8 编码）
        stem_bytes = stem.encode("utf-8")
        if len(stem_bytes) > 120:
            while len(stem.encode("utf-8")) > 120:
                stem = stem[:-1]

        last_error: Exception | None = None
        for attempt in range(self._SUBMIT_RETRIES):
            async with self._submit_limiter:
                try:
                    batch_id = await self._do_submit(client, file_path, filename, stem)
                    logger.info("MinerU task submitted: %s", batch_id)
                    return batch_id
                except Exception as e:
                    last_error = e
                    if not error_handler.is_retryable(e) or attempt == self._SUBMIT_RETRIES - 1:
                        raise
                    backoff = error_handler.get_backoff(attempt, e)
                    logger.warning("MinerU 提交失败，%.1fs 后重试 (%d/%d): %s - %s",
                                   backoff, attempt + 1, self._SUBMIT_RETRIES, filename, e)
                    await asyncio.sleep(backoff)

        raise RuntimeError(f"MinerU 提交失败（{self._SUBMIT_RETRIES} 次重试后）: {filename}") from last_error

    async def _do_submit(self, client: httpx.AsyncClient, file_path: str,
                         filename: str, stem: str) -> str:
        """实际提交逻辑"""
        # Step 1: 申请上传链接
        resp = await client.post(
            f"{self._base_url}/file-urls/batch",
            headers=self._headers(),
            json={
                "files": [{"name": filename, "data_id": stem}],
                "model_version": "vlm",
            },
        )
        resp.raise_for_status()
        body = resp.json()

        if body.get("code") != 0:
            raise RuntimeError(f"MinerU 申请上传链接失败: {body}")

        data = body.get("data", {})
        batch_id = data.get("batch_id", "")
        file_urls = data.get("file_urls", [])
        if not file_urls:
            raise RuntimeError("MinerU 未返回上传链接")

        upload_url = file_urls[0]
        if isinstance(upload_url, dict):
            upload_url = upload_url.get("url", "")

        # Step 2: 上传 PDF
        with open(file_path, "rb") as f:
            file_data = f.read()

        put_resp = await client.put(upload_url, content=file_data)
        put_resp.raise_for_status()

        return batch_id

    # --- 轮询 ---

    async def poll_task(self, task_id: str) -> str:
        """轮询直到完成，返回 result_url"""
        client = await self._get_client()
        start = monotonic()
        interval = self._poll_interval
        last_pages = -1
        stable_count = 0

        while True:
            elapsed = monotonic() - start
            if elapsed > self._timeout:
                raise TimeoutError(f"MinerU 超时 ({self._timeout}s): {task_id}")

            async with self._poll_limiter:
                resp = await client.get(
                    f"{self._base_url}/extract-results/batch/{task_id}",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                body = resp.json()

            results = (
                body.get("data", {}).get("extract_result", [])
                or body.get("data", {}).get("results", [])
            )
            if not results:
                await asyncio.sleep(interval)
                continue

            result = results[0] if isinstance(results, list) else results
            state = str(result.get("state", "")).lower()

            if state in _SUCCESS_STATES:
                zip_url = result.get("full_zip_url") or result.get("zip_url", "")
                if not zip_url:
                    raise RuntimeError(f"MinerU 完成但无结果 URL: {task_id}")
                logger.info("MinerU task completed: %s", task_id)
                return zip_url

            if state in _FAILED_STATES:
                err = result.get("error_msg", state)
                raise RuntimeError(f"MinerU 失败: {err}")

            # 自适应轮询
            extracted_pages = result.get("extracted_pages", 0)
            if extracted_pages and extracted_pages != last_pages:
                last_pages = extracted_pages
                stable_count = 0
                interval = max(1.0, interval * 0.9)
            else:
                stable_count += 1
                interval = min(10.0, interval * (1.5 if stable_count > 2 else 1.1))

            interval *= random.uniform(0.8, 1.2)
            logger.info("MinerU polling: %s, state=%s, wait=%.1fs", task_id, state, interval)
            await asyncio.sleep(interval)

    # --- 下载结果 ---

    async def fetch_result(self, task_id: str, result_url: str) -> MinerUTaskResult:
        """下载并解压 ZIP，返回解析结果"""
        client = await self._get_client()

        parsed = urlparse(result_url)
        origin = urlparse(self._base_url)
        auth = parsed.hostname == origin.hostname

        resp = await client.get(
            result_url,
            headers=self._headers(auth=auth),
        )
        resp.raise_for_status()

        paper_dir = os.path.join("./data/papers", task_id)
        images_dir = os.path.join(paper_dir, "images")
        os.makedirs(images_dir, exist_ok=True)

        pages: list[dict] = []
        md_content: str | None = None

        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            for name in zf.namelist():
                if "__MACOSX" in name or name.endswith("/"):
                    continue

                dest = os.path.join(paper_dir, name)
                os.makedirs(os.path.dirname(dest), exist_ok=True)

                if name.startswith("images/"):
                    with zf.open(name) as src, open(dest, "wb") as dst:
                        dst.write(src.read())
                elif name.endswith(".json"):
                    data = zf.read(name)
                    with open(dest, "wb") as f:
                        f.write(data)
                elif name.endswith(".md"):
                    md_content = zf.read(name).decode("utf-8", errors="replace")
                    with open(dest, "w", encoding="utf-8") as f:
                        f.write(md_content)

            # 解析 layout.json
            layout_path = os.path.join(paper_dir, "layout.json")
            if os.path.exists(layout_path):
                with open(layout_path, encoding="utf-8") as f:
                    layout = json.load(f)
                pdf_info = layout.get("pdf_info", [])
                for page_idx, page in enumerate(pdf_info):
                    blocks = page.get("para_blocks", [])
                    pages.append({"page": page_idx, "blocks": blocks})

        logger.info("MinerU result fetched: %s, %d pages", task_id, len(pages))
        return MinerUTaskResult(
            task_id=task_id,
            pages=pages,
            paper_dir=paper_dir,
            md_content=md_content,
        )

    # --- 完整流程 ---

    async def run(self, file_path: str) -> MinerUTaskResult:
        task_id = await self.submit_task(file_path)
        result_url = await self.poll_task(task_id)
        return await self.fetch_result(task_id, result_url)

    async def submit_batch(self, file_paths: list[str], concurrency: int = 10) -> list[tuple[str, str]]:
        """并发提交多个文件，返回 [(file_path, task_id), ...]"""
        import asyncio

        sem = asyncio.Semaphore(concurrency)
        results: list[tuple[str, str | None]] = []

        async def _submit_one(path: str) -> tuple[str, str | None]:
            async with sem:
                try:
                    tid = await self.submit_task(path)
                    logger.info("MinerU submitted: %s → %s", os.path.basename(path), tid)
                    return (path, tid)
                except Exception as e:
                    logger.warning("MinerU submit failed: %s → %s", os.path.basename(path), e)
                    return (path, None)

        tasks = [_submit_one(p) for p in file_paths]
        results = await asyncio.gather(*tasks)
        return results
