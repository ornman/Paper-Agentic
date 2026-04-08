# MinerU 客户端
# 这里不追求完整 SDK，只实现 Task 4 明确要求的最小能力：
# 1. 提交任务
# 2. 轮询状态
# 3. 拉取 JSON 结果
# 4. 把超时/失败/响应异常统一映射为 IngestionError

from __future__ import annotations

import time
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
        """执行完整 PDF 导入流程。"""
        submission = self.submit_task(file_path)
        state = self.poll_task(submission.task_id)

        # 先看结果地址，再看内联结果。
        # 原因是部分真实响应会返回 {result: {url: ...}}，这只是“结果位置”，不是最终正文 JSON。
        # 如果这里直接返回 state.result，就会把 url 字典误判成成功结果，制造假成功链路。
        if state.result_url:
            return self.fetch_result_json(state.result_url)
        if state.result is not None:
            return state.result
        raise IngestionError(
            code="mineru_invalid_response",
            message="MinerU 成功状态缺少结果地址",
            detail={"task_id": submission.task_id, "status": state.status},
        )

    def submit_task(self, file_path: str) -> MineruTaskSubmission:
        """提交 PDF 解析任务。"""
        payload = self._request_json(
            method="post",
            url=f"{self.base_url}/tasks",
            json={"file_path": file_path},
            error_code="mineru_submit_failed",
            error_message="MinerU 提交任务失败",
        )
        data = self._unwrap_payload(payload)
        task_id = data.get("task_id") or data.get("id")
        if not task_id:
            raise IngestionError(
                code="mineru_invalid_response",
                message="MinerU 提交结果缺少 task_id",
                detail=payload,
            )
        return MineruTaskSubmission(task_id=str(task_id))

    def poll_task(self, task_id: str) -> MineruTaskState:
        """轮询任务直到成功、失败或超时。"""
        started_at = self.monotonic_fn()
        success_statuses = {"success", "succeeded", "completed", "done"}
        failed_statuses = {"failed", "error", "cancelled", "canceled"}

        while True:
            elapsed = self.monotonic_fn() - started_at
            if elapsed > self.timeout:
                raise IngestionError(
                    code="mineru_timeout",
                    message="MinerU 处理超时",
                    detail={"task_id": task_id, "timeout": self.timeout},
                )

            payload = self._request_json(
                method="get",
                url=f"{self.base_url}/tasks/{task_id}",
                error_code="mineru_status_failed",
                error_message="MinerU 查询任务状态失败",
            )
            state = self._parse_task_state(payload)
            normalized_status = state.status.lower().strip()

            if normalized_status in success_statuses:
                return state
            if normalized_status in failed_statuses:
                raise IngestionError(
                    code="mineru_failed",
                    message=state.message or f"MinerU 任务失败: {state.status}",
                    detail={"task_id": task_id, "payload": payload},
                )

            self.sleep_fn(self.poll_interval)

    def fetch_result_json(self, result_url: str) -> dict[str, Any]:
        """拉取最终 JSON 结果。

        安全目标：
        1. 只允许同源结果地址，或显式允许的官方 CDN。
        2. 只有同源结果地址才允许携带 MinerU Bearer Token。
        3. 拒绝明显异常的结果 URL，避免把查询接口返回的外部地址直接二次请求。
        """
        normalized_result_url, should_send_authorization = self._validate_result_url(result_url)
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
