"""MinerU v4 原始 HTTP 调用

无重试、无状态。每个方法接收 token 做一次 HTTP 操作。
重试逻辑由外层 mineru_client.py 编排。
"""

from __future__ import annotations

import io
import json as _json
import logging
import time
import zipfile
from pathlib import Path

import httpx

from .result_types import MinerUProgress, MinerUResult, MinerUTaskState

logger = logging.getLogger("paper-assistant")


class MinerUApi:
    """MinerU v4 低级 HTTP 客户端"""

    def __init__(self, base_url: str, poll_interval_s: int = 5, timeout_s: int = 300):
        self._base_url = base_url
        self._poll_interval_s = poll_interval_s
        self._timeout_s = timeout_s

    async def request_upload_url(
        self, token: str, filename: str, *, page_ranges: str | None = None,
        model_version: str = "pipeline", language: str = "ch",
    ) -> tuple[str, str]:
        """POST /file-urls/batch → (batch_id, upload_url)"""
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
        files_payload: list[dict] = [{"name": filename}]
        if page_ranges:
            files_payload[0]["page_ranges"] = page_ranges

        payload = {
            "files": files_payload,
            "model_version": model_version,
            "enable_table": True,
            "language": language,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{self._base_url}/file-urls/batch", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != 0:
            raise RuntimeError(f"申请上传链接失败: {data}")

        batch_id = data["data"]["batch_id"]
        file_urls = data["data"]["file_urls"]
        if not file_urls:
            raise RuntimeError("未获取到上传链接")

        return batch_id, file_urls[0]

    async def upload_file(self, upload_url: str, file_path: Path) -> None:
        """PUT 上传文件"""
        async with httpx.AsyncClient(timeout=120) as client:
            with open(file_path, "rb") as f:
                resp = await client.put(upload_url, content=f.read())
                resp.raise_for_status()

    async def poll_batch(
        self, token: str, batch_id: str, on_progress=None,
    ) -> list[dict]:
        """轮询批量任务结果，直到全部 done/failed 或超时"""
        headers = {"Authorization": f"Bearer {token}"}
        start = time.time()

        while time.time() - start < self._timeout_s:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self._base_url}/extract-results/batch/{batch_id}", headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

            if data.get("code") != 0:
                raise RuntimeError(f"查询失败: {data}")

            results = data["data"].get("extract_result", [])
            if all(r.get("state") in ("done", "failed") for r in results):
                return results

            for r in results:
                if r.get("state") == "running":
                    progress = r.get("extract_progress", {})
                    if on_progress and progress:
                        on_progress(MinerUProgress(
                            state=MinerUTaskState.RUNNING,
                            extracted_pages=progress.get("extracted_pages", 0),
                            total_pages=progress.get("total_pages", 0),
                            message=f"解析中: {progress.get('extracted_pages', 0)}/{progress.get('total_pages', 0)} 页",
                        ))

            await _async_sleep(self._poll_interval_s)

        raise TimeoutError(f"轮询超时 ({self._timeout_s}s)")

    async def download_and_extract(self, zip_url: str) -> tuple[str, int, dict]:
        """下载 Zip 包并提取 Markdown + JSON 元数据

        Returns:
            (markdown, page_count, metadata_dict)
        """
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(zip_url)
            resp.raise_for_status()

        markdown = ""
        page_count = 0
        metadata: dict = {}
        image_paths: list[str] = []

        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            all_names = zf.namelist()

            for name in all_names:
                if name.endswith("full.md"):
                    markdown = zf.read(name).decode("utf-8")
                    break
            if not markdown:
                for name in all_names:
                    if name.endswith(".md"):
                        markdown = zf.read(name).decode("utf-8")
                        break

            for name in all_names:
                if name.endswith("layout.json"):
                    layout = _json.loads(zf.read(name).decode("utf-8"))
                    if isinstance(layout, dict) and "pdf_info" in layout:
                        page_count = len(layout["pdf_info"])
                    metadata["layout"] = layout
                    break

            for name in all_names:
                if name.endswith("content_list.json") and "v2" not in name:
                    content_list = _json.loads(zf.read(name).decode("utf-8"))
                    metadata["content_list"] = content_list
                    if not page_count:
                        page_count = max((item.get("page_idx", 0) for item in content_list), default=0) + 1
                    break

            for name in all_names:
                if name.endswith("model.json"):
                    model_data = _json.loads(zf.read(name).decode("utf-8"))
                    metadata["model"] = model_data
                    if not page_count and isinstance(model_data, list):
                        page_count = len(model_data)
                    break

            for name in all_names:
                if name.startswith("images/") and any(name.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
                    image_paths.append(name)

            if image_paths:
                metadata["image_paths"] = image_paths

        return markdown, page_count, metadata


async def _async_sleep(seconds: float):
    import asyncio
    await asyncio.sleep(seconds)
