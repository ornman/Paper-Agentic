# MinerU 客户端
# 这里不追求完整 SDK，只实现 Task 4 明确要求的最小能力：
# 1. 提交任务
# 2. 轮询状态
# 3. 拉取 JSON 结果
# 4. 把超时/失败/响应异常统一映射为 IngestionError

from __future__ import annotations

import asyncio
import random
import time
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.errors import IngestionError
from app.modules.ingestion.dto import MineruTaskState, MineruTaskSubmission


class MineruClient:
    """MinerU API 的最小同步客户端。"""

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        poll_interval: Optional[int] = None,
        timeout: Optional[int] = None,
        http_client: Any | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        monotonic_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.mineru_base_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.mineru_api_key
        self.poll_interval = poll_interval if poll_interval is not None else settings.mineru_poll_interval
        self.timeout = timeout if timeout is not None else settings.mineru_timeout
        self.http_client = http_client or httpx.Client(timeout=self.timeout)
        self.sleep_fn = sleep_fn
        self.monotonic_fn = monotonic_fn

    def run_pdf_task(self, file_path: str) -> dict[str, Any]:
        r"""执行完整 PDF 导入流程.

        返回解析后的数据，同时保存原始 MinerU JSON 到文件系统。
        """
        submission = self.submit_task(file_path)
        state = self.poll_task(submission.task_id)

        # 先看结果地址，再看内联结果。
        # 原因是部分真实响应会返回 {result: {url: ...}}，这只是"结果位置"，不是最终正文 JSON。
        # 如果这里直接返回 state.result，就会把 url 字典误判成成功结果，制造假成功链路。
        if state.result_url:
            return self.fetch_result_json(state.result_url, submission.task_id)
        if state.result is not None:
            return state.result
        raise IngestionError(
            code="mineru_invalid_response",
            message="MinerU 成功状态缺少结果地址",
            detail={"task_id": submission.task_id, "status": state.status},
        )

    def submit_task(self, file_path: str) -> MineruTaskSubmission:
        """提交 PDF 解析任务（批量上传链接方案）。"""
        from pathlib import Path
        pdf_path = Path(file_path)
        if not pdf_path.exists():
            raise IngestionError(
                code="file_not_found",
                message=f"PDF 文件不存在: {file_path}",
                detail={"file_path": file_path},
            )

        # 步骤 1: 申请上传链接
        headers = self._build_headers(include_authorization=True)
        try:
            payload = self._request_json(
                method="post",
                url=f"{self.base_url}/file-urls/batch",
                json={
                    "files": [
                        {
                            "name": pdf_path.name,
                            "data_id": pdf_path.stem  # 使用文件名作为 data_id
                        }
                    ],
                    "model_version": "vlm"
                },
                error_code="mineru_upload_url_failed",
                error_message="申请上传链接失败",
            )
            data = self._unwrap_payload(payload)

            if payload.get("code") != 0:
                raise IngestionError(
                    code="mineru_upload_url_failed",
                    message=f"申请上传链接失败: {payload.get('msg')}",
                    detail=payload,
                )

            batch_id = data.get("batch_id")
            file_urls = data.get("file_urls", [])

            if not file_urls:
                raise IngestionError(
                    code="mineru_no_upload_url",
                    message="未获取到上传链接",
                    detail=payload,
                )

            upload_url = file_urls[0]

            # 步骤 2: 上传文件
            with open(pdf_path, "rb") as f:
                upload_response = self.http_client.put(upload_url, data=f)
                upload_response.raise_for_status()

            # 系统会自动提交解析任务，使用 batch_id 作为 task_id
            return MineruTaskSubmission(task_id=batch_id)

        except IngestionError:
            raise
        except Exception as exc:
            raise IngestionError(
                code="mineru_submit_failed",
                message="MinerU 提交任务失败",
                detail=str(exc),
            ) from exc

    def poll_task(self, task_id: str) -> MineruTaskState:
        """轮询批量任务直到成功、失败或超时（带自适应间隔）.

        🔴 P0-4 优化：
        1. 根据任务进度动态调整轮询间隔（指数退避）
        2. 添加抖动避免多个任务同时轮询
        3. 最小间隔 1 秒，最大间隔 10 秒
        """
        started_at = self.monotonic_fn()
        success_statuses = {"success", "succeeded", "completed", "done"}
        failed_statuses = {"failed", "error", "cancelled", "canceled"}

        # 🔴 P0-4 优化：自适应轮询间隔
        # 初始间隔：2 秒（从配置读取）
        # 最小间隔：1 秒
        # 最大间隔：10 秒
        current_interval = float(self.poll_interval)
        min_interval = 1.0
        max_interval = 10.0

        last_progress = None
        stable_count = 0  # 进度稳定计数

        while True:
            elapsed = self.monotonic_fn() - started_at
            if elapsed > self.timeout:
                raise IngestionError(
                    code="mineru_timeout",
                    message="MinerU 处理超时",
                    detail={"batch_id": task_id, "timeout": self.timeout},
                )

            # 使用批量查询端点
            payload = self._request_json(
                method="get",
                url=f"{self.base_url}/extract-results/batch/{task_id}",
                error_code="mineru_status_failed",
                error_message="MinerU 查询任务状态失败",
            )

            # 批量查询返回的是 extract_result 数组
            data = self._unwrap_payload(payload)
            extract_result = data.get("extract_result", [])

            if not extract_result:
                raise IngestionError(
                    code="mineru_invalid_response",
                    message="批量查询结果为空",
                    detail=payload,
                )

            # 取第一个文件的结果
            result = extract_result[0]
            state = result.get("state", "").lower()

            if state in success_statuses:
                return MineruTaskState(
                    status=result.get("state", "done"),
                    result_url=result.get("full_zip_url"),
                    result=None,
                    message=result.get("err_msg", ""),
                )
            if state in failed_statuses:
                raise IngestionError(
                    code="mineru_failed",
                    message=result.get("err_msg") or f"MinerU 任务失败: {state}",
                    detail={"batch_id": task_id, "result": result},
                )

            # 🔴 P0-4 优化：根据进度动态调整间隔
            progress = result.get("extract_progress", {})
            if progress:
                extracted = progress.get("extracted_pages", 0)
                total = progress.get("total_pages", 0)

                # 进度变化时显示
                if extracted != last_progress:
                    print(f"[MinerU] 解析进度: {extracted}/{total} 页")
                    last_progress = extracted
                    stable_count = 0
                    # 🔴 有进度时保持当前间隔或稍作缩短
                    current_interval = max(min_interval, current_interval * 0.9)
                else:
                    stable_count += 1
                    # 🔴 进度稳定时逐渐延长间隔（指数退避）
                    if stable_count > 2:
                        current_interval = min(max_interval, current_interval * 1.5)
            else:
                # 🔴 无进度信息时使用默认退避
                current_interval = min(max_interval, current_interval * 1.1)

            # 🔴 P0-4 优化：添加抖动，避免多个任务同时轮询
            jitter = random.uniform(0.8, 1.2)
            actual_interval = current_interval * jitter

            print(f"[MinerU] 等待 {actual_interval:.1f} 秒后重试...")

            self.sleep_fn(actual_interval)

    def fetch_result_json(self, result_url: str, task_id: str) -> dict[str, Any]:
        """拉取最终 JSON 结果。

        安全目标：
        1. 只允许同源结果地址，或显式允许的官方 CDN。
        2. 只有同源结果地址才允许携带 MinerU Bearer Token。
        3. 拒绝明显异常的结果 URL，避免把查询接口返回的外部地址直接二次请求。

        处理流程：
        1. 如果 result_url 指向 ZIP 文件，下载并解压
        2. 保存原始 JSON 文件到 data/papers/{task_id}/
        3. 从 ZIP 文件中提取 content_list.json
        4. 返回解析后的 JSON 对象

        Args:
            result_url: MinerU 结果 URL（指向 ZIP 文件）
            task_id: 批量任务 ID，用作保存目录名
        """
        import json
        import tempfile
        import zipfile
        from urllib.parse import unquote

        normalized_result_url, should_send_authorization = self._validate_result_url(result_url)

        # 检查是否为 ZIP 文件
        if normalized_result_url.endswith('.zip'):
            # 创建保存目录
            papers_dir = Path("./data/papers")
            papers_dir.mkdir(parents=True, exist_ok=True)
            task_dir = papers_dir / task_id
            task_dir.mkdir(exist_ok=True)

            # 下载 ZIP 文件
            headers = self._build_headers(include_authorization=should_send_authorization)
            try:
                response = self.http_client.get(normalized_result_url, headers=headers, timeout=self.timeout)
                response.raise_for_status()

                # 保存到临时文件
                with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
                    tmp_file.write(response.content)
                    tmp_path = tmp_file.name

                # 创建图片保存目录
                images_dir = task_dir / "images"
                images_dir.mkdir(exist_ok=True)

                # 解压并保存所有文件
                with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
                    # 文件列表
                    file_list = zip_ref.namelist()

                    # 提取并保存 JSON 和图片文件
                    for zip_path in file_list:
                        if zip_path.startswith('__MACOSX') or zip_path.endswith('/'):
                            continue

                        # 计算保存路径
                        if zip_path.startswith('images/'):
                            # 图片文件：保存到 images/ 目录
                            file_name = Path(zip_path).name
                            save_path = images_dir / file_name

                            # 解压并保存图片
                            with zip_ref.open(zip_path) as source_file:
                                with open(save_path, 'wb') as target_file:
                                    target_file.write(source_file.read())

                            print(f"[MinerU] 保存图片: {file_name}")

                        elif zip_path.endswith('.json'):
                            # JSON 文件：直接保存到 task_dir
                            file_name = Path(zip_path).name
                            save_path = task_dir / file_name

                            # 解压并保存
                            with zip_ref.open(zip_path) as source_file:
                                with open(save_path, 'wb') as target_file:
                                    target_file.write(source_file.read())

                            print(f"[MinerU] 保存原始文件: {save_path.name}")

                    # 从 layout.json 读取完整结构（包括图片）
                    layout_files = [f for f in file_list if f == 'layout.json' and not f.startswith('__MACOSX')]

                    if layout_files:
                        # 使用 layout.json（包含完整信息）
                        with zip_ref.open('layout.json') as f:
                            layout_data = json.load(f)

                        # 从 layout.json 提取页面信息
                        pdf_info = layout_data.get('pdf_info', [])

                        if not isinstance(pdf_info, list):
                            raise IngestionError(
                                code="mineru_invalid_response",
                                message="layout.json 中 pdf_info 不是列表",
                                detail={"pdf_info_type": type(pdf_info).__name__},
                            )

                        # 转换为标准 pages 格式
                        pages = []
                        for page_item in pdf_info:
                            if not isinstance(page_item, dict):
                                continue

                            page_idx = page_item.get('page_idx')
                            para_blocks = page_item.get('para_blocks', [])

                            if not isinstance(para_blocks, list):
                                continue

                            pages.append({
                                'page': page_idx,
                                'blocks': para_blocks
                            })

                        data = {'pages': pages}
                    else:
                        raise IngestionError(
                            code="mineru_invalid_response",
                            message="ZIP 文件中未找到 layout.json",
                            detail={"file_list": file_list},
                        )

                # 清理临时文件
                Path(tmp_path).unlink()

                if not isinstance(data, dict):
                    raise IngestionError(
                        code="mineru_invalid_response",
                        message=f"MinerU 结果不是 JSON 对象（从 {json_file} 读取）",
                        detail={"data_type": type(data).__name__},
                    )

                return data

            except IngestionError:
                raise
            except Exception as exc:
                raise IngestionError(
                    code="mineru_result_failed",
                    message=f"MinerU 拉取结果失败: {exc}",
                    detail=str(exc),
                ) from exc
        else:
            # 原有的 JSON 处理逻辑
            payload = self._request_json(
                method="get",
                url=normalized_result_url,
                error_code="mineru_result_failed",
                error_message="MinerU 拉取结果失败",
                include_authorization=should_send_authorization,
            )
            data = self._unwrap_payload(payload)
            if not isinstance(data, dict):
                raise IngestionError(
                    code="mineru_invalid_response",
                    message="MinerU 结果不是 JSON 对象",
                    detail=payload,
                )
            return data

    def _request_json(
        self,
        *,
        method: str,
        url: str,
        error_code: str,
        error_message: str,
        json: dict[str, Any] | None = None,
        include_authorization: bool = True,
    ) -> dict[str, Any]:
        """统一发送请求并解析 JSON。"""
        headers = self._build_headers(include_authorization=include_authorization)
        try:
            if method == "post":
                response = self.http_client.post(url, headers=headers, json=json)
            else:
                response = self.http_client.get(url, headers=headers)
            response.raise_for_status()
            payload = response.json()
        except IngestionError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise IngestionError(code=error_code, message=error_message, detail=str(exc)) from exc

        if not isinstance(payload, dict):
            raise IngestionError(
                code="mineru_invalid_response",
                message="MinerU 返回的不是 JSON 对象",
                detail=payload,
            )
        return payload

    def _build_headers(self, *, include_authorization: bool = True) -> dict[str, str]:
        """构造最小请求头。"""
        headers = {"Accept": "application/json"}
        if include_authorization and self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _unwrap_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """兼容 top-level 与 data 包裹两种常见返回格式。"""
        data = payload.get("data")
        if isinstance(data, dict):
            return data
        return payload

    def _validate_result_url(self, result_url: str) -> tuple[str, bool]:
        """校验结果 URL，并决定是否允许携带 Authorization。

        返回值含义：
        - 第一个值：规范化后的结果 URL
        - 第二个值：该请求是否允许携带 MinerU Bearer Token
        """
        normalized_result_url = result_url.strip()
        parsed_result_url = urlsplit(normalized_result_url)
        if parsed_result_url.scheme not in {"http", "https"}:
            raise IngestionError(
                code="mineru_invalid_result_url",
                message="MinerU 结果地址协议不合法",
                detail={"result_url": result_url},
            )
        if not parsed_result_url.netloc:
            raise IngestionError(
                code="mineru_invalid_result_url",
                message="MinerU 结果地址缺少主机名",
                detail={"result_url": result_url},
            )

        base_origin = self._build_origin(self.base_url)
        result_origin = self._build_origin(normalized_result_url)
        result_host = (parsed_result_url.hostname or "").lower()
        allowed_result_hosts = {"cdn-mineru.openxlab.org.cn"}

        if result_origin == base_origin:
            return normalized_result_url, True
        if result_host in allowed_result_hosts:
            return normalized_result_url, False

        raise IngestionError(
            code="mineru_invalid_result_url",
            message="结果地址主机不在允许列表",
            detail={"result_url": result_url, "allowed_hosts": sorted(allowed_result_hosts)},
        )

    def _build_origin(self, url: str) -> str:
        """提取并归一化 URL origin，用于同源校验。"""
        parsed_url = urlsplit(url)
        scheme = parsed_url.scheme.lower()
        hostname = (parsed_url.hostname or "").lower()
        port = self._normalize_origin_port(scheme, parsed_url.port)

        if not hostname:
            return ""
        if port is None:
            return f"{scheme}://{hostname}"
        return f"{scheme}://{hostname}:{port}"

    def _normalize_origin_port(self, scheme: str, port: int | None) -> int | None:
        """归一化默认端口，避免 `https://host` 和 `https://host:443` 被误判为不同源。"""
        default_ports = {"http": 80, "https": 443}
        default_port = default_ports.get(scheme)
        if port is None or port == default_port:
            return None
        return port

    def _parse_task_state(self, payload: dict[str, Any]) -> MineruTaskState:
        """把原始轮询响应归一化为统一状态对象。"""
        data = self._unwrap_payload(payload)
        status = data.get("status")
        if not isinstance(status, str) or not status.strip():
            raise IngestionError(
                code="mineru_invalid_response",
                message="MinerU 状态响应缺少 status",
                detail=payload,
            )

        raw_result = data.get("result")
        result = raw_result if isinstance(raw_result, dict) else None

        # 这里先显式校验可选字符串字段，再进入 Pydantic。
        # 原因是这些字段一旦类型漂移，应该稳定映射成业务语义 `mineru_invalid_response`，
        # 而不是把 ValidationError 漏到上层后再被包成通用 ingestion_failed。
        top_level_result_url = self._read_optional_string_field(data, "result_url")
        nested_result_url = self._read_optional_string_field(result, "url") if isinstance(result, dict) else None
        message = self._read_optional_string_field(data, "message")
        error_message = self._read_optional_string_field(data, "error_message")

        try:
            return MineruTaskState(
                status=status,
                result_url=top_level_result_url or nested_result_url,
                result=result,
                message=message or error_message,
            )
        except ValidationError as exc:
            raise IngestionError(
                code="mineru_invalid_response",
                message="MinerU 状态响应字段类型非法",
                detail=exc.errors(),
            ) from exc

    def _read_optional_string_field(self, data: dict[str, Any] | None, field_name: str) -> str | None:
        """读取可选字符串字段，并把类型漂移稳定映射成业务错误。"""
        if not isinstance(data, dict) or field_name not in data:
            return None

        value = data.get(field_name)
        if value is None:
            return None
        if not isinstance(value, str):
            raise IngestionError(
                code="mineru_invalid_response",
                message=f"MinerU 状态响应字段 {field_name} 必须是字符串",
                detail={"field_name": field_name, "field_type": type(value).__name__},
            )

        normalized_value = value.strip()
        if not normalized_value:
            return None
        return normalized_value
