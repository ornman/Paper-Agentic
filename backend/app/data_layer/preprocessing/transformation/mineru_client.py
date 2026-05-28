"""MinerU 精准解析 API 客户端

封装 MinerU v4 API 的完整生命周期：
提交 → 上传 → 轮询 → 下载 → 解包

内置自动重试（抖动 + 指数退避）和状态实时回调。
超限 PDF 自动切分：检测页数/文件大小 → 按段上传 → 拼接结果。
"""

from __future__ import annotations

import io
import json as _json
import logging
import random
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import os

import httpx

logger = logging.getLogger("paper-assistant")

# ── 常量 ──────────────────────────────────────────────────
_MINERU_V4_BASE = os.environ.get("MINERU_BASE_URL", "https://mineru.net/api/v4")
_DEFAULT_TIMEOUT_S = 300
_POLL_INTERVAL_S = 5

# MinerU v4 API 限制
MAX_PAGES_PER_CHUNK = 180      # 留 20 页安全余量（实际限制 200）
MAX_FILE_SIZE_BYTES = 190 * 1024 * 1024  # 190MB（实际限制 200MB）


class MinerUTaskState(str, Enum):
    """MinerU 任务状态"""
    PENDING = "pending"
    UPLOADING = "uploading"
    RUNNING = "running"
    CONVERTING = "converting"
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True)
class MinerUResult:
    """MinerU 解析结果"""
    markdown: str
    page_count: int
    char_count: int
    success: bool
    error: str | None = None
    task_state: str = ""
    elapsed_s: float = 0.0
    metadata: dict = field(default_factory=dict)  # JSON 元数据（layout、content_list、model、image_paths）
    logs: list[dict] = field(default_factory=list)
    split_count: int = 1  # 切分段数（1 = 未切分）


@dataclass
class MinerUProgress:
    """MinerU 进度信息"""
    state: MinerUTaskState
    extracted_pages: int = 0
    total_pages: int = 0
    message: str = ""


# ── 回调类型 ──────────────────────────────────────────────
ProgressCallback = callable  # (MinerUProgress) -> None


class MinerUClient:
    """MinerU 精准解析 API 客户端

    特性：
    - 自动重试：抖动 + 指数退避，最多 max_retries 次
    - 状态回调：每次轮询触发 on_progress 回调
    - 超时保护：单次任务最长 timeout_s 秒
    - 超限切分：页数/文件大小超限时自动切分、逐段上传、拼接结果
    """

    def __init__(
        self,
        token: str,
        *,
        max_retries: int = 3,
        base_delay_s: float = 30.0,
        jitter_s: float = 5.0,
        timeout_s: int = _DEFAULT_TIMEOUT_S,
        poll_interval_s: int = _POLL_INTERVAL_S,
        on_progress: ProgressCallback | None = None,
    ):
        self._token = token
        self._max_retries = max_retries
        self._base_delay_s = base_delay_s
        self._jitter_s = jitter_s
        self._timeout_s = timeout_s
        self._poll_interval_s = poll_interval_s
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

        超限处理：
        - 页数 > MAX_PAGES_PER_CHUNK：按段切分，逐段上传，拼接结果
        - 文件大小 > MAX_FILE_SIZE_BYTES：同上
        - 切分后的结果自动拼接（markdown、content_list、model、layout）

        Args:
            file_path: PDF 文件路径
            page_ranges: 页码范围，如 "1-20"（切分时忽略此参数）
            model_version: 模型版本 (pipeline / vlm / MinerU-HTML)
            language: 文档语言

        Returns:
            MinerUResult
        """
        logs: list[dict] = []
        t0 = time.perf_counter()

        # ── Router：探查并判断是否需要切分 ──
        page_count = _get_pdf_page_count(file_path)
        file_size = file_path.stat().st_size
        is_pdf = file_path.suffix.lower() == ".pdf"
        needs_split = (
            is_pdf  # 非 PDF 文件不切分（MinerU 原生处理）
            and page_ranges is None  # 用户指定了 page_ranges 就不切分
            and (
                page_count > MAX_PAGES_PER_CHUNK
                or file_size > MAX_FILE_SIZE_BYTES
            )
        )

        if needs_split:
            chunks = _compute_chunks(page_count, MAX_PAGES_PER_CHUNK)
            logs.append(_log("info",
                f"PDF 超限，自动切分: {page_count} 页, {file_size // 1024 // 1024}MB → {len(chunks)} 段",
                page_count=page_count,
                file_size_mb=file_size // 1024 // 1024,
                chunk_count=len(chunks),
                chunk_ranges=chunks,
            ))
            self._emit_progress(
                MinerUTaskState.UPLOADING,
                total_pages=page_count,
                message=f"PDF 超限，切分为 {len(chunks)} 段",
            )
            return await self._parse_split(
                file_path,
                chunks=chunks,
                model_version=model_version,
                language=language,
                logs=logs,
                t0=t0,
            )

        # ── 单段解析 ──
        return await self._parse_single(
            file_path,
            page_ranges=page_ranges,
            model_version=model_version,
            language=language,
            logs=logs,
            t0=t0,
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
        """单文件解析（带重试）"""
        for attempt in range(self._max_retries):
            try:
                result = await self._attempt_parse(
                    file_path,
                    page_ranges=page_ranges,
                    model_version=model_version,
                    language=language,
                    logs=logs,
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

                if attempt < self._max_retries - 1:
                    delay = self._retry_delay(attempt)
                    logs.append(_log("warning", f"解析失败，{delay:.1f}s 后重试 (attempt {attempt + 1}): {result.error}"))
                    await _async_sleep(delay)
                else:
                    return result

            except Exception as e:
                if attempt < self._max_retries - 1:
                    delay = self._retry_delay(attempt)
                    logs.append(_log("warning", f"异常，{delay:.1f}s 后重试 (attempt {attempt + 1}): {e}"))
                    await _async_sleep(delay)
                else:
                    logs.append(_log("error", f"重试耗尽: {e}"))
                    return MinerUResult(
                        markdown="",
                        page_count=0,
                        char_count=0,
                        success=False,
                        error=str(e),
                        elapsed_s=round(time.perf_counter() - t0, 2),
                        logs=logs,
                    )

        return MinerUResult(
            markdown="",
            page_count=0,
            char_count=0,
            success=False,
            error="重试耗尽",
            elapsed_s=round(time.perf_counter() - t0, 2),
            logs=logs,
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
        """切分后逐段解析，最后拼接结果

        断点续传：每个 chunk 独立重试，成功即保留，失败记录但不丢弃已完成的。
        去重：已成功的 chunk 不会重复解析。
        """
        from pypdf import PdfReader, PdfWriter

        reader = PdfReader(str(file_path))
        total_pages = len(reader.pages)

        # 已完成 chunk 的结果（按索引存储，支持断点续传）
        completed: dict[int, dict] = {}
        failed_chunks: list[str] = []
        page_offset = 0

        for i, chunk_range in enumerate(chunks):
            start, end = _parse_page_range(chunk_range)
            chunk_pages = end - start + 1

            # 去重：跳过已成功的 chunk
            if i in completed:
                logs.append(_log("info", f"切分段 {i+1}/{len(chunks)}: 页 {start}-{end} 已完成，跳过"))
                page_offset += chunk_pages
                continue

            logs.append(_log("info", f"切分段 {i+1}/{len(chunks)}: 页 {start}-{end}"))
            self._emit_progress(
                MinerUTaskState.UPLOADING,
                extracted_pages=page_offset,
                total_pages=total_pages,
                message=f"解析切分段 {i+1}/{len(chunks)}: 页 {start}-{end}",
            )

            # 写出临时 PDF
            writer = PdfWriter()
            for p in range(start - 1, end):  # pypdf 0-indexed
                writer.add_page(reader.pages[p])

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp_path = Path(tmp.name)
                writer.write(tmp)

            try:
                # 每个 chunk 独立重试
                chunk_result = None
                for attempt in range(self._max_retries):
                    result = await self._parse_single(
                        tmp_path,
                        page_ranges=None,
                        model_version=model_version,
                        language=language,
                        logs=logs,
                        t0=t0,
                    )

                    if result.success:
                        chunk_result = result
                        break

                    if attempt < self._max_retries - 1:
                        delay = self._retry_delay(attempt)
                        logs.append(_log("warning",
                            f"切分段 {i+1} 第{attempt+1}次失败，{delay:.1f}s 后重试: {result.error}",
                        ))
                        await _async_sleep(delay)
                    else:
                        logs.append(_log("error",
                            f"切分段 {i+1} 重试耗尽（{self._max_retries}次）: {result.error}",
                        ))

                if chunk_result is None:
                    # 该 chunk 全部重试失败，记录但继续处理后续 chunk
                    failed_chunks.append(chunk_range)
                    page_offset += chunk_pages
                    continue

                # 成功：保存结果，调整 page_idx 偏移
                meta = chunk_result.metadata
                completed[i] = {
                    "markdown": chunk_result.markdown,
                    "content_list": _adjust_content_list_page_idx(
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

        # 拼接已完成的结果（按 chunk 顺序）
        all_markdown = []
        all_content_list = []
        all_model = []
        all_layout_pdf_info = []
        all_image_paths = []

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
        error = None
        if not success:
            error = f"{len(failed_chunks)}/{len(chunks)} 段失败: {failed_chunks}"

        logs.append(_log(
            "info" if success else "warning",
            f"切分拼接完成: {len(completed)}/{len(chunks)} 段成功, "
            f"{page_offset} 页, {len(merged_markdown)} chars",
        ))

        return MinerUResult(
            markdown=merged_markdown,
            page_count=page_offset,
            char_count=len(merged_markdown),
            success=success,
            error=error,
            elapsed_s=round(time.perf_counter() - t0, 2),
            metadata=merged_metadata,
            logs=logs,
            split_count=len(chunks),
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
        """单次解析尝试"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._token}",
        }

        # 1. 申请上传链接
        self._emit_progress(MinerUTaskState.UPLOADING, message="申请上传链接")
        logs.append(_log("info", "申请上传链接"))

        files_payload: list[dict] = [{"name": file_path.name}]
        if page_ranges:
            files_payload[0]["page_ranges"] = page_ranges

        payload = {
            "files": files_payload,
            "model_version": model_version,
            "enable_table": True,
            "language": language,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{_MINERU_V4_BASE}/file-urls/batch",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != 0:
            raise RuntimeError(f"申请上传链接失败: {data}")

        batch_id = data["data"]["batch_id"]
        file_urls = data["data"]["file_urls"]

        if not file_urls:
            raise RuntimeError("未获取到上传链接")

        logs.append(_log("info", f"获取上传链接成功, batch_id={batch_id}"))

        # 2. 上传文件
        self._emit_progress(MinerUTaskState.UPLOADING, message="上传文件中")
        logs.append(_log("info", f"上传文件: {file_path.name} ({file_path.stat().st_size} bytes)"))

        async with httpx.AsyncClient(timeout=120) as client:
            with open(file_path, "rb") as f:
                upload_resp = await client.put(file_urls[0], content=f.read())
                upload_resp.raise_for_status()

        logs.append(_log("info", "上传完成"))

        # 3. 轮询结果
        self._emit_progress(MinerUTaskState.RUNNING, message="解析中")
        logs.append(_log("info", "开始轮询解析结果"))

        results = await self._poll_batch(batch_id, logs)

        if not results or results[0].get("state") != "done":
            state = results[0].get("state", "unknown") if results else "no_result"
            err_msg = results[0].get("err_msg", "未知错误") if results else "无结果"
            logs.append(_log("error", f"解析未完成: state={state}, err={err_msg}"))
            return MinerUResult(
                markdown="",
                page_count=0,
                char_count=0,
                success=False,
                error=err_msg,
                task_state=state,
                logs=logs,
            )

        # 4. 下载结果
        zip_url = results[0].get("full_zip_url")
        if not zip_url:
            logs.append(_log("error", "无下载链接"))
            return MinerUResult(
                markdown="",
                page_count=0,
                char_count=0,
                success=False,
                error="无下载链接",
                task_state="done",
                logs=logs,
            )

        self._emit_progress(MinerUTaskState.DONE, message="下载结果中")
        logs.append(_log("info", "下载解析结果"))

        markdown, page_count, metadata = await self._download_and_extract(zip_url, logs)

        return MinerUResult(
            markdown=markdown,
            page_count=page_count,
            char_count=len(markdown),
            success=True,
            task_state="done",
            metadata=metadata,
            logs=logs,
        )

    async def _poll_batch(
        self,
        batch_id: str,
        logs: list[dict],
    ) -> list[dict]:
        """轮询批量任务结果"""
        headers = {"Authorization": f"Bearer {self._token}"}
        start = time.time()

        while time.time() - start < self._timeout_s:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{_MINERU_V4_BASE}/extract-results/batch/{batch_id}",
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

            if data.get("code") != 0:
                raise RuntimeError(f"查询失败: {data}")

            results = data["data"].get("extract_result", [])
            all_done = all(
                r.get("state") in ("done", "failed")
                for r in results
            )

            if all_done:
                return results

            for r in results:
                state = r.get("state")
                progress = r.get("extract_progress", {})
                if state == "running" and progress:
                    extracted = progress.get("extracted_pages", 0)
                    total = progress.get("total_pages", 0)
                    self._emit_progress(
                        MinerUTaskState.RUNNING,
                        extracted_pages=extracted,
                        total_pages=total,
                        message=f"解析中: {extracted}/{total} 页",
                    )

            await _async_sleep(self._poll_interval_s)

        raise TimeoutError(f"轮询超时 ({self._timeout_s}s)")

    async def _download_and_extract(
        self,
        zip_url: str,
        logs: list[dict],
    ) -> tuple[str, int, dict]:
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

            # 1. 提取 Markdown
            for name in all_names:
                if name.endswith("full.md"):
                    markdown = zf.read(name).decode("utf-8")
                    break
            if not markdown:
                for name in all_names:
                    if name.endswith(".md"):
                        markdown = zf.read(name).decode("utf-8")
                        break

            # 2. 提取 layout.json
            for name in all_names:
                if name.endswith("layout.json"):
                    layout = _json.loads(zf.read(name).decode("utf-8"))
                    if isinstance(layout, dict) and "pdf_info" in layout:
                        page_count = len(layout["pdf_info"])
                    metadata["layout"] = layout
                    break

            # 3. 提取 content_list.json（v1 优先，排除 v2）
            for name in all_names:
                if name.endswith("content_list.json") and "v2" not in name:
                    content_list = _json.loads(zf.read(name).decode("utf-8"))
                    metadata["content_list"] = content_list
                    if not page_count:
                        page_count = max((item.get("page_idx", 0) for item in content_list), default=0) + 1
                    break

            # 4. 提取 model.json
            for name in all_names:
                if name.endswith("model.json"):
                    model_data = _json.loads(zf.read(name).decode("utf-8"))
                    metadata["model"] = model_data
                    if not page_count and isinstance(model_data, list):
                        page_count = len(model_data)
                    break

            # 5. 收集图片路径
            for name in all_names:
                if name.startswith("images/") and any(name.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
                    image_paths.append(name)

            if image_paths:
                metadata["image_paths"] = image_paths

        if not markdown:
            logs.append(_log("warning", "Zip 包中未找到 Markdown 文件"))
        else:
            logs.append(_log("info", f"提取完成: {len(markdown)} chars, {page_count} pages, {len(image_paths)} images"))

        return markdown, page_count, metadata

    def retry_delay(self, attempt: int) -> float:
        """计算重试延迟（抖动 + 指数退避）"""
        return self._base_delay_s * (2 ** attempt) + random.uniform(0, self._jitter_s)

    def _retry_delay(self, attempt: int) -> float:
        return self.retry_delay(attempt)

    def _emit_progress(
        self,
        state: MinerUTaskState,
        *,
        extracted_pages: int = 0,
        total_pages: int = 0,
        message: str = "",
    ):
        """触发进度回调"""
        if self._on_progress:
            try:
                self._on_progress(MinerUProgress(
                    state=state,
                    extracted_pages=extracted_pages,
                    total_pages=total_pages,
                    message=message,
                ))
            except Exception:
                pass


# ── 工具函数 ──────────────────────────────────────────────

def _get_pdf_page_count(file_path: Path) -> int:
    """获取 PDF 页数（轻量，不读取全部内容）。非 PDF 返回 0。"""
    if file_path.suffix.lower() != ".pdf":
        return 0
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(file_path))
        return len(reader.pages)
    except Exception:
        return 0


def _compute_chunks(total_pages: int, max_pages: int) -> list[str]:
    """计算切分段的页码范围列表

    Returns:
        ["1-180", "181-360", ...] 格式的页码范围列表
    """
    chunks = []
    start = 1
    while start <= total_pages:
        end = min(start + max_pages - 1, total_pages)
        chunks.append(f"{start}-{end}")
        start = end + 1
    return chunks


def _parse_page_range(range_str: str) -> tuple[int, int]:
    """解析页码范围字符串

    Args:
        range_str: "1-180" 格式

    Returns:
        (start, end) 1-indexed
    """
    parts = range_str.split("-")
    return int(parts[0]), int(parts[1])


def _adjust_content_list_page_idx(
    content_list: list[dict],
    offset: int,
) -> list[dict]:
    """调整 content_list 中所有条目的 page_idx 偏移

    返回新列表，不修改原数据。
    """
    if offset == 0:
        return content_list

    adjusted = []
    for item in content_list:
        new_item = dict(item)
        if "page_idx" in new_item:
            new_item["page_idx"] = new_item["page_idx"] + offset
        adjusted.append(new_item)
    return adjusted


def _log(level: str, message: str, **kwargs) -> dict:
    """生成日志条目"""
    import datetime
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "level": level,
        "message": message,
    }
    entry.update(kwargs)
    return entry


async def _async_sleep(seconds: float):
    """异步休眠"""
    import asyncio
    await asyncio.sleep(seconds)
