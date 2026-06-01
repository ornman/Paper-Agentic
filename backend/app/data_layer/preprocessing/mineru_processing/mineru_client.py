"""MinerU 编排器

职责：决定是否切分 → 通过 Key 池获取 token → 调用 api_client → 重试 → 拼接结果。
配置统一从 BackendSettings 读取，不硬编码。
"""

from __future__ import annotations

import logging
import random
import time
from pathlib import Path

from .api_client import MinerUApi
from .key_pool import ApiKeyPool
from .pdf_splitter import (
    adjust_content_list_page_idx,
    compute_chunks,
    get_pdf_page_count,
    needs_split,
    parse_page_range,
    split_pdf,
)
from .result_types import MinerUProgress, MinerUResult, MinerUTaskState, ProgressCallback

logger = logging.getLogger("paper-assistant")


class MinerUClient:
    """MinerU 精准解析编排器

    特性：
    - 指数退避 + jitter 重试
    - Key 池轮转（当前单 Key 直通，3+ Key 时自动启用）
    - 进度回调
    - 超限 PDF 自动切分、逐段上传、拼接结果
    """

    def __init__(
        self,
        token: str,
        *,
        base_url: str = "",
        max_retries: int = 0,
        base_delay_s: float = 30.0,
        jitter_s: float = 5.0,
        timeout_s: int = 0,
        poll_interval_s: int = 0,
        on_progress: ProgressCallback | None = None,
    ):
        from app.service_layer.config.settings import get_settings
        _s = get_settings()
        self._pool = ApiKeyPool([token], max_per_key=_s.mineru_max_per_key)
        self._api = MinerUApi(
            base_url or _s.mineru_base_url or "https://mineru.net/api/v4",
            poll_interval_s=poll_interval_s or _s.mineru_poll_interval,
            timeout_s=timeout_s or _s.mineru_timeout,
        )
        self._max_retries = max_retries or _s.mineru_max_retries
        self._base_delay_s = base_delay_s
        self._jitter_s = jitter_s
        self._on_progress = on_progress

    async def parse_document(
        self,
        file_path: Path,
        *,
        page_ranges: str | None = None,
        model_version: str = "pipeline",
        language: str = "ch",
    ) -> MinerUResult:
        """解析 PDF 文件

        流程：探查页数/大小 → 判断是否切分 → 上传 → 轮询 → 下载结果
        """
        logs: list[dict] = []
        t0 = time.perf_counter()

        if needs_split(file_path, page_ranges):
            from .pdf_splitter import get_pdf_page_count as _gpc
            page_count = _gpc(file_path)
            chunks = compute_chunks(page_count)
            self._emit_progress(
                MinerUTaskState.UPLOADING,
                total_pages=page_count,
                message=f"PDF 超限，切分为 {len(chunks)} 段",
            )
            return await self._parse_split(
                file_path, chunks=chunks,
                model_version=model_version, language=language,
                logs=logs, t0=t0,
            )

        return await self._parse_single(
            file_path, page_ranges=page_ranges,
            model_version=model_version, language=language,
            logs=logs, t0=t0,
        )

    async def _parse_single(
        self,
        file_path: Path,
        *,
        page_ranges: str | None,
        model_version: str,
        language: str,
        logs: list[dict],
        t0: float,
    ) -> MinerUResult:
        """单文件解析（带重试 + Key 轮转）"""
        last_error = ""

        for attempt in range(self._max_retries):
            try:
                result = await self._attempt_parse(
                    file_path, page_ranges=page_ranges,
                    model_version=model_version, language=language, logs=logs,
                )
                result = MinerUResult(
                    markdown=result.markdown,
                    page_count=result.page_count,
                    char_count=result.char_count,
                    success=result.success,
                    error=result.error,
                    task_state=result.task_state,
                    elapsed_s=round(time.perf_counter() - t0, 2),
                    metadata=result.metadata,
                    logs=logs,
                )
                if result.success:
                    return result
                last_error = result.error or "解析失败"

            except Exception as e:
                last_error = str(e)

            if attempt < self._max_retries - 1:
                delay = self._retry_delay(attempt)
                logs.append(_log("warning", f"第{attempt+1}次失败，{delay:.1f}s 后重试: {last_error}"))
                await _async_sleep(delay)

        logs.append(_log("error", f"重试耗尽（{self._max_retries}次）: {last_error}"))
        return MinerUResult(
            markdown="", page_count=0, char_count=0,
            success=False, error=last_error,
            elapsed_s=round(time.perf_counter() - t0, 2), logs=logs,
        )

    async def _parse_split(
        self,
        file_path: Path,
        *,
        chunks: list[str],
        model_version: str,
        language: str,
        logs: list[dict],
        t0: float,
    ) -> MinerUResult:
        """切分后逐段解析，最后拼接结果"""
        page_count = get_pdf_page_count(file_path)
        completed: dict[int, dict] = {}
        failed_chunks: list[str] = []
        page_offset = 0

        for i, chunk_range in enumerate(chunks):
            start, end = parse_page_range(chunk_range)
            chunk_pages = end - start + 1

            self._emit_progress(
                MinerUTaskState.UPLOADING,
                extracted_pages=page_offset,
                total_pages=page_count,
                message=f"解析切分段 {i+1}/{len(chunks)}: 页 {start}-{end}",
            )

            tmp_path = split_pdf(file_path, chunk_range)
            try:
                chunk_result = None
                for attempt in range(self._max_retries):
                    result = await self._parse_single(
                        tmp_path, page_ranges=None,
                        model_version=model_version, language=language,
                        logs=logs, t0=t0,
                    )
                    if result.success:
                        chunk_result = result
                        break
                    if attempt < self._max_retries - 1:
                        delay = self._retry_delay(attempt)
                        await _async_sleep(delay)

                if chunk_result is None:
                    failed_chunks.append(chunk_range)
                    page_offset += chunk_pages
                    continue

                meta = chunk_result.metadata
                completed[i] = {
                    "markdown": chunk_result.markdown,
                    "content_list": adjust_content_list_page_idx(
                        meta.get("content_list", []), page_offset,
                    ),
                    "model": meta.get("model", []),
                    "layout_pdf_info": (
                        meta["layout"].get("pdf_info", [])
                        if isinstance(meta.get("layout"), dict) else []
                    ),
                    "image_paths": meta.get("image_paths", []),
                }
                page_offset += chunk_pages
            finally:
                tmp_path.unlink(missing_ok=True)

        all_markdown, all_content_list, all_model = [], [], []
        all_layout_pdf_info, all_image_paths = [], []

        for i in sorted(completed.keys()):
            c = completed[i]
            all_markdown.append(c["markdown"])
            all_content_list.extend(c["content_list"])
            all_model.extend(c["model"])
            all_layout_pdf_info.extend(c["layout_pdf_info"])
            all_image_paths.extend(c["image_paths"])

        merged_markdown = "\n\n".join(all_markdown)
        merged_metadata = {}
        if all_content_list:
            merged_metadata["content_list"] = all_content_list
        if all_model:
            merged_metadata["model"] = all_model
        if all_layout_pdf_info:
            merged_metadata["layout"] = {"pdf_info": all_layout_pdf_info}
        if all_image_paths:
            merged_metadata["image_paths"] = all_image_paths

        success = len(failed_chunks) == 0
        return MinerUResult(
            markdown=merged_markdown, page_count=page_offset,
            char_count=len(merged_markdown), success=success,
            error=f"{len(failed_chunks)}/{len(chunks)} 段失败" if not success else None,
            elapsed_s=round(time.perf_counter() - t0, 2),
            metadata=merged_metadata, logs=logs, split_count=len(chunks),
        )

    async def _attempt_parse(
        self,
        file_path: Path,
        *,
        page_ranges: str | None,
        model_version: str,
        language: str,
        logs: list[dict],
    ) -> MinerUResult:
        """单次解析：submit → upload → poll → download"""

        # 1. 申请上传链接
        self._emit_progress(MinerUTaskState.UPLOADING, message="申请上传链接")
        async with self._pool.acquire() as token:
            batch_id, upload_url = await self._api.request_upload_url(
                token, file_path.name, page_ranges=page_ranges,
                model_version=model_version, language=language,
            )

            # 2. 上传文件
            self._emit_progress(MinerUTaskState.UPLOADING, message="上传文件中")
            await self._api.upload_file(upload_url, file_path)

            # 3. 轮询结果
            self._emit_progress(MinerUTaskState.RUNNING, message="解析中")
            results = await self._api.poll_batch(token, batch_id, on_progress=self._on_progress)

        if not results or results[0].get("state") != "done":
            state = results[0].get("state", "unknown") if results else "no_result"
            err_msg = results[0].get("err_msg", "未知错误") if results else "无结果"
            return MinerUResult(
                markdown="", page_count=0, char_count=0,
                success=False, error=err_msg, task_state=state, logs=logs,
            )

        # 4. 下载结果
        zip_url = results[0].get("full_zip_url")
        if not zip_url:
            return MinerUResult(
                markdown="", page_count=0, char_count=0,
                success=False, error="无下载链接", task_state="done", logs=logs,
            )

        self._emit_progress(MinerUTaskState.DONE, message="下载结果中")
        markdown, page_count, metadata = await self._api.download_and_extract(zip_url)

        return MinerUResult(
            markdown=markdown, page_count=page_count,
            char_count=len(markdown), success=True,
            task_state="done", metadata=metadata, logs=logs,
        )

    def _retry_delay(self, attempt: int) -> float:
        return self._base_delay_s * (2 ** attempt) + random.uniform(0, self._jitter_s)

    def _emit_progress(self, state: MinerUTaskState, **kwargs) -> None:
        if self._on_progress:
            try:
                self._on_progress(MinerUProgress(state=state, **kwargs))
            except Exception:
                pass


def _log(level: str, message: str, **kwargs) -> dict:
    import datetime
    entry = {"timestamp": datetime.datetime.now().isoformat(), "level": level, "message": message}
    entry.update(kwargs)
    return entry


async def _async_sleep(seconds: float):
    import asyncio
    await asyncio.sleep(seconds)
