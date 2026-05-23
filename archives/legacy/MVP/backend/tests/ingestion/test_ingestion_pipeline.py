# Task 4: MinerU 导入编排与清洗入口测试
#
# 这里严格按 TDD 先定义行为，再补实现。
# 测试范围只覆盖当前任务要求的最小能力：
# 1. MinerU 客户端能提交任务、轮询状态、拉取 JSON 结果。
# 2. 清洗逻辑能过滤页眉页脚、页码、短噪音块、重复块。
# 3. library.import_pdf() 会触发 ingestion.service 导入链路。
# 4. MinerU 超时时，文档状态会被标记为 failed，并记录错误阶段与错误信息。
# 5. Task 4 安全回归：本地 PDF 路径边界、结果 URL 校验、跨主机授权头约束。

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.core.errors import IngestionError
from app.repositories import sqlite_repo


class _FakeHttpResponse:
    """最小假响应对象。

    这里只实现 MineruClient 会用到的两个接口：
    - raise_for_status
    - json

    这样测试就不会依赖真实网络，也不会被 httpx 的更多细节绑死。
    """

    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        """模拟 HTTP 错误抛出。"""
        if self.status_code >= 400:
            raise RuntimeError(f"http error: {self.status_code}")

    def json(self) -> dict:
        """返回预设 JSON。"""
        return self._payload


class _FakeHttpClient:
    """按顺序回放响应的假 HTTP 客户端。"""

    def __init__(self, *, post_responses: list[_FakeHttpResponse], get_responses: list[_FakeHttpResponse]) -> None:
        self._post_responses = list(post_responses)
        self._get_responses = list(get_responses)
        self.post_calls: list[dict[str, object | None]] = []
        self.get_calls: list[dict[str, object | None]] = []

    def post(self, url: str, *, headers: dict | None = None, json: dict | None = None):
        """记录请求并返回预设响应。"""
        self.post_calls.append({"url": url, "json": json, "headers": headers})
        if not self._post_responses:
            raise AssertionError("没有为 POST 请求准备响应")
        return self._post_responses.pop(0)

    def get(self, url: str, *, headers: dict | None = None):
        """记录请求并返回预设响应。"""
        self.get_calls.append({"url": url, "headers": headers})
        if not self._get_responses:
            raise AssertionError("没有为 GET 请求准备响应")
        return self._get_responses.pop(0)


class _FakeMonotonic:
    """可控的单调时钟，避免测试真的等待超时。"""

    def __init__(self, values: list[float]) -> None:
        self._values = list(values)

    def __call__(self) -> float:
        if not self._values:
            raise AssertionError("FakeMonotonic 已没有更多时间值")
        return self._values.pop(0)


class _FakeMineruSuccessClient:
    """返回成功 MinerU 结果的假客户端。"""

    def __init__(self, expected_path: str) -> None:
        self.expected_path = expected_path

    def run_pdf_task(self, file_path: str) -> dict:
        assert file_path == self.expected_path
        return {
            "pages": [
                {
                    "page": 1,
                    "blocks": [
                        {"text": "会议论文集 2026"},
                        {"text": "第 1 页"},
                        {"text": "这是第一段有效正文。"},
                        {"text": "这是第一段有效正文。"},
                        {"text": "好"},
                    ],
                },
                {
                    "page": 2,
                    "blocks": [
                        {"text": "会议论文集 2026"},
                        {"text": "2"},
                        {"text": "这是第二段有效正文。"},
                    ],
                },
            ]
        }


class _FakeMineruTimeoutClient:
    """模拟 MinerU 超时。"""

    def __init__(self, expected_path: str) -> None:
        self.expected_path = expected_path

    def run_pdf_task(self, file_path: str) -> dict:
        assert file_path == self.expected_path
        raise IngestionError(code="mineru_timeout", message="MinerU 处理超时")


class _UnexpectedIngestionService:
    """用于断言非法路径不会进入导入编排。"""

    def ingest_document(self, record):  # noqa: ANN001
        del record
        raise AssertionError("非法文件路径不应触发 ingestion.service")


def _use_temp_sqlite_database(monkeypatch) -> Path:
    """切换到项目内临时 SQLite，避免污染真实数据。"""
    backend_root = Path(__file__).resolve().parents[2]
    temp_dir = backend_root / "data" / "test-temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(temp_dir)
    db_path = temp_dir / f"ingestion-task4-{uuid.uuid4()}.db"
    monkeypatch.setenv("SQLITE_DB_PATH", str(db_path))
    get_settings.cache_clear()
    sqlite_repo._engine = None
    return db_path


def _create_temp_pdf(name: str) -> Path:
    """创建一个最小本地 PDF 文件供 import_pdf 路径校验通过。"""
    backend_root = Path(__file__).resolve().parents[2]
    temp_dir = backend_root / "data" / "test-temp" / "pdf-fixtures"
    temp_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = temp_dir / f"{uuid.uuid4()}-{name}"
    pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
    return pdf_path


def _create_temp_text_file(name: str, content: str) -> Path:
    """创建一个项目内临时文本文件，避免依赖系统 tmp 目录。"""
    backend_root = Path(__file__).resolve().parents[2]
    temp_dir = backend_root / "data" / "test-temp" / "text-fixtures"
    temp_dir.mkdir(parents=True, exist_ok=True)
    text_file_path = temp_dir / f"{uuid.uuid4()}-{name}"
    text_file_path.write_text(content, encoding="utf-8")
    return text_file_path


def test_mineru_client_submits_polls_and_fetches_same_origin_result_json(monkeypatch):
    """same-origin 的 result_url 必须继续可用，避免把正常链路误杀。"""
    _use_temp_sqlite_database(monkeypatch)

    from app.modules.ingestion.mineru_client import MineruClient

    fake_http_client = _FakeHttpClient(
        post_responses=[
            _FakeHttpResponse(200, {"task_id": "task-123"}),
        ],
        get_responses=[
            _FakeHttpResponse(200, {"status": "processing"}),
            _FakeHttpResponse(200, {"status": "succeeded", "result_url": "https://mineru.local/result/task-123"}),
            _FakeHttpResponse(200, {"pages": [{"page": 1, "blocks": [{"text": "正文段落"}]}]}),
        ],
    )
    client = MineruClient(
        base_url="https://mineru.local/api/v4",
        api_key="secret-token",
        http_client=fake_http_client,
        poll_interval=0,
        timeout=10,
        sleep_fn=lambda _seconds: None,
        monotonic_fn=_FakeMonotonic([0.0, 0.1, 0.2]),
    )

    result = client.run_pdf_task("D:/papers/success.pdf")

    assert result["pages"][0]["blocks"][0]["text"] == "正文段落"
    assert fake_http_client.post_calls == [
        {
            "url": "https://mineru.local/api/v4/tasks",
            "json": {"file_path": "D:/papers/success.pdf"},
            "headers": {"Accept": "application/json", "Authorization": "Bearer secret-token"},
        }
    ]
    assert [call["url"] for call in fake_http_client.get_calls] == [
        "https://mineru.local/api/v4/tasks/task-123",
        "https://mineru.local/api/v4/tasks/task-123",
        "https://mineru.local/result/task-123",
    ]
    assert fake_http_client.get_calls[-1]["headers"] == {
        "Accept": "application/json",
        "Authorization": "Bearer secret-token",
    }


def test_mineru_client_fetches_final_json_when_success_payload_uses_nested_result_url(monkeypatch):
    """轮询成功若只返回 result.url，客户端也必须继续拉最终 JSON。"""
    _use_temp_sqlite_database(monkeypatch)

    from app.modules.ingestion.mineru_client import MineruClient

    fake_http_client = _FakeHttpClient(
        post_responses=[
            _FakeHttpResponse(200, {"task_id": "task-456"}),
        ],
        get_responses=[
            _FakeHttpResponse(
                200,
                {"status": "succeeded", "result": {"url": "https://mineru.local/result/task-456"}},
            ),
            _FakeHttpResponse(200, {"pages": [{"page": 1, "blocks": [{"text": "嵌套地址后的正文"}]}]}),
        ],
    )
    client = MineruClient(
        base_url="https://mineru.local/api/v4",
        api_key="secret-token",
        http_client=fake_http_client,
        poll_interval=0,
        timeout=10,
        sleep_fn=lambda _seconds: None,
        monotonic_fn=_FakeMonotonic([0.0, 0.1]),
    )

    result = client.run_pdf_task("D:/papers/success.pdf")

    assert result["pages"][0]["blocks"][0]["text"] == "嵌套地址后的正文"
    assert [call["url"] for call in fake_http_client.get_calls] == [
        "https://mineru.local/api/v4/tasks/task-456",
        "https://mineru.local/result/task-456",
    ]


def test_mineru_client_fetches_allowed_cdn_result_without_authorization(monkeypatch):
    """官方允许的 CDN 结果地址可以拉取，但不能携带 MinerU Bearer Token。"""
    _use_temp_sqlite_database(monkeypatch)

    from app.modules.ingestion.mineru_client import MineruClient

    fake_http_client = _FakeHttpClient(
        post_responses=[
            _FakeHttpResponse(200, {"task_id": "task-cdn"}),
        ],
        get_responses=[
            _FakeHttpResponse(
                200,
                {"status": "succeeded", "result_url": "https://cdn-mineru.openxlab.org.cn/results/task-cdn.json"},
            ),
            _FakeHttpResponse(200, {"pages": [{"page": 1, "blocks": [{"text": "CDN 正文"}]}]}),
        ],
    )
    client = MineruClient(
        base_url="https://mineru.local/api/v4",
        api_key="secret-token",
        http_client=fake_http_client,
        poll_interval=0,
        timeout=10,
        sleep_fn=lambda _seconds: None,
        monotonic_fn=_FakeMonotonic([0.0, 0.1]),
    )

    result = client.run_pdf_task("D:/papers/success.pdf")

    assert result["pages"][0]["blocks"][0]["text"] == "CDN 正文"
    assert [call["url"] for call in fake_http_client.get_calls] == [
        "https://mineru.local/api/v4/tasks/task-cdn",
        "https://cdn-mineru.openxlab.org.cn/results/task-cdn.json",
    ]
    assert fake_http_client.get_calls[-1]["headers"] == {"Accept": "application/json"}


@pytest.mark.parametrize(
    ("base_url", "result_url"),
    [
        ("https://mineru.local:443/api/v4", "https://mineru.local/result/task-443"),
        ("http://mineru.local:80/api/v4", "http://mineru.local/result/task-80"),
    ],
)
def test_mineru_client_treats_explicit_default_port_as_same_origin(monkeypatch, base_url: str, result_url: str):
    """显式默认端口与隐式默认端口必须视为同源。"""
    _use_temp_sqlite_database(monkeypatch)

    from app.modules.ingestion.mineru_client import MineruClient

    fake_http_client = _FakeHttpClient(
        post_responses=[
            _FakeHttpResponse(200, {"task_id": "task-default-port"}),
        ],
        get_responses=[
            _FakeHttpResponse(200, {"status": "succeeded", "result_url": result_url}),
            _FakeHttpResponse(200, {"pages": [{"page": 1, "blocks": [{"text": "默认端口同源正文"}]}]}),
        ],
    )
    client = MineruClient(
        base_url=base_url,
        api_key="secret-token",
        http_client=fake_http_client,
        poll_interval=0,
        timeout=10,
        sleep_fn=lambda _seconds: None,
        monotonic_fn=_FakeMonotonic([0.0, 0.1]),
    )

    result = client.run_pdf_task("D:/papers/success.pdf")

    assert result["pages"][0]["blocks"][0]["text"] == "默认端口同源正文"
    assert fake_http_client.get_calls[-1]["headers"] == {
        "Accept": "application/json",
        "Authorization": "Bearer secret-token",
    }


@pytest.mark.parametrize(
    ("poll_payload", "expected_field_name"),
    [
        ({"status": "succeeded", "result_url": ["https://mineru.local/result/task-bad"]}, "result_url"),
        (
            {
                "status": "succeeded",
                "result_url": "https://mineru.local/result/task-bad-message",
                "message": {"text": "bad"},
            },
            "message",
        ),
    ],
)
def test_mineru_client_maps_invalid_optional_string_fields_to_invalid_response(
    monkeypatch,
    poll_payload: dict,
    expected_field_name: str,
):
    """轮询响应中的可选字符串字段类型漂移时，必须统一落到 invalid_response。"""
    _use_temp_sqlite_database(monkeypatch)

    from app.modules.ingestion.mineru_client import MineruClient

    fake_http_client = _FakeHttpClient(
        post_responses=[
            _FakeHttpResponse(200, {"task_id": "task-invalid-field"}),
        ],
        get_responses=[
            _FakeHttpResponse(200, poll_payload),
        ],
    )
    client = MineruClient(
        base_url="https://mineru.local/api/v4",
        api_key="secret-token",
        http_client=fake_http_client,
        poll_interval=0,
        timeout=10,
        sleep_fn=lambda _seconds: None,
        monotonic_fn=_FakeMonotonic([0.0, 0.1]),
    )

    with pytest.raises(IngestionError) as exc_info:
        client.run_pdf_task("D:/papers/success.pdf")

    assert exc_info.value.code == "mineru_invalid_response"
    assert expected_field_name in exc_info.value.message



def test_mineru_client_rejects_untrusted_external_result_url(monkeypatch):
    """非同源且非白名单主机的结果地址必须被拒绝，避免二阶 SSRF。"""
    _use_temp_sqlite_database(monkeypatch)

    from app.modules.ingestion.mineru_client import MineruClient

    fake_http_client = _FakeHttpClient(
        post_responses=[
            _FakeHttpResponse(200, {"task_id": "task-evil"}),
        ],
        get_responses=[
            _FakeHttpResponse(
                200,
                {"status": "succeeded", "result_url": "https://evil.example.com/result/task-evil.json"},
            ),
        ],
    )
    client = MineruClient(
        base_url="https://mineru.local/api/v4",
        api_key="secret-token",
        http_client=fake_http_client,
        poll_interval=0,
        timeout=10,
        sleep_fn=lambda _seconds: None,
        monotonic_fn=_FakeMonotonic([0.0, 0.1]),
    )

    with pytest.raises(IngestionError, match="结果地址主机不在允许列表"):
        client.run_pdf_task("D:/papers/success.pdf")

    assert [call["url"] for call in fake_http_client.get_calls] == [
        "https://mineru.local/api/v4/tasks/task-evil",
    ]


def test_clean_mineru_payload_filters_headers_page_numbers_short_noise_and_duplicates():
    """清洗入口必须只保留真正正文块。"""
    from app.modules.ingestion.cleaning import clean_mineru_payload

    cleaned_document = clean_mineru_payload(
        document_id="doc-1",
        title="测试文档",
        file_path="D:/papers/success.pdf",
        index_mode="brute",
        payload={
            "pages": [
                {
                    "page": 1,
                    "blocks": [
                        {"text": "会议论文集 2026"},
                        {"text": "第 1 页"},
                        {"text": "这是第一段有效正文。"},
                        {"text": "这是第一段有效正文。"},
                        {"text": "好"},
                    ],
                },
                {
                    "page": 2,
                    "blocks": [
                        {"text": "会议论文集 2026"},
                        {"text": "2"},
                        {"text": "这是第二段有效正文。"},
                    ],
                },
            ]
        },
    )

    assert [block.text for block in cleaned_document.blocks] == [
        "这是第一段有效正文。",
        "这是第二段有效正文。",
    ]
    assert cleaned_document.raw_block_count == 8
    assert cleaned_document.cleaned_block_count == 2
    assert cleaned_document.removed_block_count == 6


def test_library_import_pdf_rejects_remote_url(monkeypatch):
    """import_pdf 只接受本地文件路径，不能直接收 URL。"""
    _use_temp_sqlite_database(monkeypatch)

    from app.modules.library.repository import LibraryRepository
    from app.modules.library.service import LibraryService

    service = LibraryService(repository=LibraryRepository(), ingestion_service=_UnexpectedIngestionService())

    with pytest.raises(ValueError, match="本地 PDF 文件路径"):
        service.import_pdf("https://evil.test/paper.pdf")

    assert service.list_documents() == []


def test_library_import_pdf_rejects_unc_network_path(monkeypatch):
    """UNC 网络路径会把导入边界扩展到远端共享，必须在服务层挡住。"""
    _use_temp_sqlite_database(monkeypatch)

    from app.modules.library.repository import LibraryRepository
    from app.modules.library.service import LibraryService

    service = LibraryService(repository=LibraryRepository(), ingestion_service=_UnexpectedIngestionService())

    with pytest.raises(ValueError, match="本地 PDF 文件路径"):
        service.import_pdf("//server/share/paper.pdf")

    assert service.list_documents() == []


def test_library_import_pdf_rejects_non_pdf_file(monkeypatch):
    """导入入口只应接受 PDF，避免把 Task 4 的语义再次放宽。"""
    _use_temp_sqlite_database(monkeypatch)

    from app.modules.library.repository import LibraryRepository
    from app.modules.library.service import LibraryService

    text_file_path = _create_temp_text_file("note.txt", "not a pdf")

    service = LibraryService(repository=LibraryRepository(), ingestion_service=_UnexpectedIngestionService())

    with pytest.raises(ValueError, match=".pdf"):
        service.import_pdf(str(text_file_path))

    assert service.list_documents() == []


def test_library_import_pdf_rejects_missing_file(monkeypatch):
    """文件不存在时必须尽早失败，不能落一条伪 pending 记录。"""
    _use_temp_sqlite_database(monkeypatch)

    from app.modules.library.repository import LibraryRepository
    from app.modules.library.service import LibraryService

    backend_root = Path(__file__).resolve().parents[2]
    missing_dir = backend_root / "data" / "test-temp" / "missing-fixtures"
    missing_dir.mkdir(parents=True, exist_ok=True)
    missing_pdf_path = missing_dir / f"{uuid.uuid4()}-missing.pdf"
    service = LibraryService(repository=LibraryRepository(), ingestion_service=_UnexpectedIngestionService())

    with pytest.raises(ValueError, match="不存在"):
        service.import_pdf(str(missing_pdf_path))

    assert service.list_documents() == []


def test_library_import_pdf_runs_ingestion_pipeline_to_completed(monkeypatch):
    """library.import_pdf 必须通过 ingestion.service 推进状态到 completed。"""
    _use_temp_sqlite_database(monkeypatch)

    from app.modules.ingestion.service import IngestionService
    from app.modules.library.repository import LibraryRepository
    from app.modules.library.service import LibraryService

    pdf_path = _create_temp_pdf("success.pdf")
    repository = LibraryRepository()
    ingestion_service = IngestionService(
        repository=repository,
        mineru_client=_FakeMineruSuccessClient(expected_path=str(pdf_path)),
    )
    service = LibraryService(repository=repository, ingestion_service=ingestion_service)

    result = service.import_pdf(
        file_path=str(pdf_path),
        title="成功文档",
        index_mode="brute",
        tags=["task4"],
    )

    reloaded = service.get_document(result.document_id)

    assert result.status == "completed"
    assert reloaded.status == "completed"
    assert reloaded.title == "成功文档"
    assert reloaded.error_stage is None
    assert reloaded.error_message is None


def test_ingestion_pipeline_marks_document_failed_when_mineru_times_out(monkeypatch):
    """MinerU 超时时，导入链路必须落到 failed，而不是停在中间态。"""
    _use_temp_sqlite_database(monkeypatch)

    from app.modules.ingestion.service import IngestionService
    from app.modules.library.repository import LibraryRepository
    from app.modules.library.service import LibraryService

    pdf_path = _create_temp_pdf("paper.pdf")
    repository = LibraryRepository()
    ingestion_service = IngestionService(
        repository=repository,
        mineru_client=_FakeMineruTimeoutClient(expected_path=str(pdf_path)),
    )
    service = LibraryService(repository=repository, ingestion_service=ingestion_service)

    result = service.import_pdf(
        file_path=str(pdf_path),
        title="超时文档",
        index_mode="brute",
    )

    assert result.status == "failed"
    assert result.error_stage == "ingestion"
    assert "超时" in (result.error_message or "")


def test_ingestion_pipeline_marks_document_failed_when_cleaned_document_has_no_valid_blocks(monkeypatch):
    """清洗后若没有有效正文块，导入链路必须落为 failed。"""
    _use_temp_sqlite_database(monkeypatch)

    from app.modules.ingestion.service import IngestionService
    from app.modules.library.repository import LibraryRepository
    from app.modules.library.service import LibraryService

    pdf_path = _create_temp_pdf("empty.pdf")

    class _FakeMineruEmptyBlocksClient:
        """返回会被清洗规则全部过滤掉的假结果。"""

        def __init__(self, expected_path: str) -> None:
            self.expected_path = expected_path

        def run_pdf_task(self, file_path: str) -> dict:
            assert file_path == self.expected_path
            return {
                "pages": [
                    {
                        "page": 1,
                        "blocks": [
                            {"text": "会议论文集 2026"},
                            {"text": "第 1 页"},
                            {"text": "好"},
                        ],
                    },
                    {
                        "page": 2,
                        "blocks": [
                            {"text": "会议论文集 2026"},
                            {"text": "2"},
                        ],
                    },
                ]
            }

    repository = LibraryRepository()
    ingestion_service = IngestionService(
        repository=repository,
        mineru_client=_FakeMineruEmptyBlocksClient(expected_path=str(pdf_path)),
    )
    service = LibraryService(repository=repository, ingestion_service=ingestion_service)

    result = service.import_pdf(
        file_path=str(pdf_path),
        title="空正文文档",
        index_mode="brute",
    )
    reloaded = service.get_document(result.document_id)

    assert result.status == "failed"
    assert reloaded.status == "failed"
    assert result.error_stage == "ingestion"
    assert "无有效正文" in (result.error_message or "")



@pytest.mark.parametrize(
    ("invalid_payload", "expected_message"),
    [
        ({"pages": None}, "pages 必须是数组"),
        ({"pages": {}}, "pages 必须是数组"),
        ({"pages": [123]}, "pages[0] 必须是对象"),
    ],
)
def test_ingestion_pipeline_marks_document_failed_when_success_payload_pages_shape_is_invalid(
    monkeypatch,
    invalid_payload: dict,
    expected_message: str,
):
    """成功态里 pages 结构漂移时，必须落到 invalid_response，而不是误报空正文。"""
    _use_temp_sqlite_database(monkeypatch)

    from app.modules.ingestion.service import IngestionService
    from app.modules.library.repository import LibraryRepository
    from app.modules.library.service import LibraryService

    pdf_path = _create_temp_pdf("invalid-pages-shape.pdf")

    class _FakeMineruInvalidPagesPayloadClient:
        """返回 pages 字段结构漂移的假结果。"""

        def __init__(self, expected_path: str, payload: dict) -> None:
            self.expected_path = expected_path
            self.payload = payload

        def run_pdf_task(self, file_path: str) -> dict:
            assert file_path == self.expected_path
            return self.payload

    repository = LibraryRepository()
    ingestion_service = IngestionService(
        repository=repository,
        mineru_client=_FakeMineruInvalidPagesPayloadClient(expected_path=str(pdf_path), payload=invalid_payload),
    )
    service = LibraryService(repository=repository, ingestion_service=ingestion_service)

    result = service.import_pdf(
        file_path=str(pdf_path),
        title="pages 结构漂移文档",
        index_mode="brute",
    )
    reloaded = service.get_document(result.document_id)

    assert result.status == "failed"
    assert reloaded.status == "failed"
    assert result.error_stage == "ingestion"
    assert result.error_message == expected_message



def test_ingestion_pipeline_marks_document_failed_when_success_payload_shape_is_invalid(monkeypatch):
    """成功态如果返回结构漂移的 payload，必须落到 invalid_response，而不是误归因为空正文。"""
    _use_temp_sqlite_database(monkeypatch)

    from app.modules.ingestion.service import IngestionService
    from app.modules.library.repository import LibraryRepository
    from app.modules.library.service import LibraryService

    pdf_path = _create_temp_pdf("invalid-success-shape.pdf")

    class _FakeMineruInvalidSuccessPayloadClient:
        """返回成功态但结构不符合当前 Task 4 最小契约的假结果。"""

        def __init__(self, expected_path: str) -> None:
            self.expected_path = expected_path

        def run_pdf_task(self, file_path: str) -> dict:
            assert file_path == self.expected_path
            return {"unexpected": "shape"}

    repository = LibraryRepository()
    ingestion_service = IngestionService(
        repository=repository,
        mineru_client=_FakeMineruInvalidSuccessPayloadClient(expected_path=str(pdf_path)),
    )
    service = LibraryService(repository=repository, ingestion_service=ingestion_service)

    result = service.import_pdf(
        file_path=str(pdf_path),
        title="结构漂移文档",
        index_mode="brute",
    )
    reloaded = service.get_document(result.document_id)

    assert result.status == "failed"
    assert reloaded.status == "failed"
    assert result.error_stage == "ingestion"
    assert result.error_message == "MinerU 成功结果缺少最小正文结构字段"
