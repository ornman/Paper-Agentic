# MVP Backend Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 重构现有 FastAPI 后端为模块化单体，实现 MinerU 驱动的 PDF 导入、双索引模式、四场景加权检索，以及 DeepSeek 驱动的带来源问答。

**Architecture:** 保留现有 FastAPI 壳、SQLite/Chroma/BM25 基础设施，按 `session`、`library`、`ingestion`、`indexing`、`retrieval`、`qa` 重新切分业务模块。问答链路采用确定性编排，不做真 Agent；所有向量写入与检索严格锁定 `Qwen/Qwen3-Embedding-8B` 的 `1536` 维配置。

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, ChromaDB, rank_bm25 + jieba, httpx, DeepSeek API, SiliconFlow Embedding/Rerank, MinerU API, pytest.

---

## Implementation Rules

- 执行时使用 `@superpowers:executing-plans`
- 每个任务严格先写测试，再写最小实现，再跑测试
- 每个完成块都运行验证命令，不要跳过
- 需要查 WPSJS / DeepSeek / MinerU / SiliconFlow 文档时，优先使用本地 micro-rag：`D:/同步/.tools/rag`
- `EMBEDDING_MODEL` 固定 `Qwen/Qwen3-Embedding-8B`
- `EMBEDDING_DIMENSIONS` 固定 `1536`
- 不允许把维度改成 `4096`

---

### Task 1: 建立测试基础与环境配置基线

**Files:**
- Create: `backend/.env.example`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/core/test_config_contract.py`
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/core/config.py`

**Step 1: Write the failing test**

```python
def test_embedding_dimension_is_pinned_to_1536():
    settings = Settings(embedding_model="Qwen/Qwen3-Embedding-8B", embedding_dimension=1536)
    assert settings.embedding_dimension == 1536
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/core/test_config_contract.py -v`
Expected: FAIL because test file / validation does not exist yet.

**Step 3: Write minimal implementation**

- 在 `backend/app/core/config.py` 中新增：
  - `DEEPSEEK_BASE_URL`
  - `DEEPSEEK_API_KEY`
  - `DEEPSEEK_MODEL`
  - `SILICONFLOW_API_KEY`
  - `SILICONFLOW_BASE_URL`
  - `EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B`
  - `EMBEDDING_DIMENSIONS=1536`
  - `RERANK_MODEL=Qwen/Qwen3-Reranker-8B`
  - `MINERU_*`
- 添加配置校验：若模型不是 `Qwen/Qwen3-Embedding-8B` 或维度不是 `1536`，启动时报错。
- 在 `backend/.env.example` 中写入所有占位变量。
- 在 `backend/pyproject.toml` 中补充 `pytest`、`pytest-asyncio`。

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/core/test_config_contract.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/.env.example backend/tests/conftest.py backend/tests/core/test_config_contract.py backend/pyproject.toml backend/app/core/config.py
git commit -m "feat: pin backend model config baseline"
```

---

### Task 2: 建立模块化目录骨架与公共错误模型

**Files:**
- Create: `backend/app/core/errors.py`
- Create: `backend/app/modules/__init__.py`
- Create: `backend/app/modules/session/__init__.py`
- Create: `backend/app/modules/library/__init__.py`
- Create: `backend/app/modules/ingestion/__init__.py`
- Create: `backend/app/modules/indexing/__init__.py`
- Create: `backend/app/modules/retrieval/__init__.py`
- Create: `backend/app/modules/qa/__init__.py`
- Create: `backend/tests/core/test_error_contract.py`

**Step 1: Write the failing test**

```python
def test_domain_error_exposes_stage_and_message():
    err = DomainError(code="retrieval_failed", stage="retrieval", message="boom")
    assert err.stage == "retrieval"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/core/test_error_contract.py -v`
Expected: FAIL because `DomainError` does not exist.

**Step 3: Write minimal implementation**

- 在 `backend/app/core/errors.py` 中创建统一错误类型：
  - `DomainError`
  - `ConfigError`
  - `IngestionError`
  - `IndexingError`
  - `RetrievalError`
  - `QAError`
- 让错误对象最少包含：`code`、`stage`、`message`、`detail`。
- 建立 `modules/` 目录骨架，后续任务在这里落代码。

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/core/test_error_contract.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/core/errors.py backend/app/modules backend/tests/core/test_error_contract.py
git commit -m "refactor: add modular backend skeleton"
```

---

### Task 3: 重建 library 模块与文档状态机

**Files:**
- Create: `backend/app/modules/library/models.py`
- Create: `backend/app/modules/library/repository.py`
- Create: `backend/app/modules/library/service.py`
- Create: `backend/app/api/v1/routes/library.py`
- Create: `backend/tests/library/test_document_state_machine.py`
- Modify: `backend/app/api/v1/router.py`
- Modify: `backend/app/repositories/sqlite_repo.py`

**Step 1: Write the failing test**

```python
def test_document_status_can_progress_to_completed():
    record = DocumentRecord(status="pending")
    record = record.transition("parsing")
    record = record.transition("cleaning")
    record = record.transition("indexing")
    record = record.transition("completed")
    assert record.status == "completed"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/library/test_document_state_machine.py -v`
Expected: FAIL because document model/state machine does not exist.

**Step 3: Write minimal implementation**

- 为文档库建立持久化模型：
  - `document_id`
  - `title`
  - `file_path`
  - `index_mode`
  - `status`
  - `tags`
  - `error_stage`
  - `error_message`
- 支持状态：`pending/parsing/cleaning/indexing/completed/failed/deleting/deleted`
- 新增 `library` 路由：
  - `POST /api/v1/library/import`
  - `GET /api/v1/library/documents`
  - `DELETE /api/v1/library/documents/{document_id}`
  - `POST /api/v1/library/documents/{document_id}/reindex`

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/library/test_document_state_machine.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/modules/library backend/app/api/v1/routes/library.py backend/app/api/v1/router.py backend/app/repositories/sqlite_repo.py backend/tests/library/test_document_state_machine.py
git commit -m "feat: add document library state machine"
```

---

### Task 4: 实现 MinerU 导入编排与清洗入口

**Files:**
- Create: `backend/app/modules/ingestion/dto.py`
- Create: `backend/app/modules/ingestion/mineru_client.py`
- Create: `backend/app/modules/ingestion/cleaning.py`
- Create: `backend/app/modules/ingestion/service.py`
- Create: `backend/tests/ingestion/test_ingestion_pipeline.py`
- Modify: `backend/app/modules/library/service.py`

**Step 1: Write the failing test**

```python
def test_ingestion_pipeline_marks_document_failed_when_mineru_times_out(fake_library_service):
    result = fake_library_service.import_pdf("D:/paper.pdf", "brute")
    assert result.status in {"pending", "parsing", "failed"}
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/ingestion/test_ingestion_pipeline.py -v`
Expected: FAIL because ingestion service/mineru client does not exist.

**Step 3: Write minimal implementation**

- 实现 `MineruClient`：
  - 提交任务
  - 轮询状态
  - 拉取 JSON 结果
  - 超时/失败映射为 `IngestionError`
- 实现 `cleaning.py`：
  - 页眉页脚过滤
  - 页码清理
  - 短噪音块过滤
  - 重复块过滤
- 让 `library.import_pdf()` 调用 `ingestion.service` 启动导入链路。

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/ingestion/test_ingestion_pipeline.py -v`
Expected: PASS with mocked MinerU responses.

**Step 5: Commit**

```bash
git add backend/app/modules/ingestion backend/app/modules/library/service.py backend/tests/ingestion/test_ingestion_pipeline.py
git commit -m "feat: add mineru ingestion pipeline"
```

---

### Task 5: 实现双索引模式与维度守卫

**Files:**
- Create: `backend/app/modules/indexing/dto.py`
- Create: `backend/app/modules/indexing/chunkers/brute.py`
- Create: `backend/app/modules/indexing/chunkers/parent_child.py`
- Create: `backend/app/modules/indexing/chroma_repo.py`
- Create: `backend/app/modules/indexing/bm25_repo.py`
- Create: `backend/app/modules/indexing/service.py`
- Create: `backend/tests/indexing/test_index_modes.py`
- Modify: `backend/app/clients/embedding_client.py`

**Step 1: Write the failing test**

```python
def test_parent_child_index_mode_builds_parent_and_child_records():
    result = build_parent_child_index(sample_cleaned_document())
    assert result.parent_blocks
    assert result.child_chunks
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/indexing/test_index_modes.py -v`
Expected: FAIL because chunkers/service do not exist.

**Step 3: Write minimal implementation**

- 实现 `brute`：500~1000 token 切块 + 重叠
- 实现 `parent_child`：父块/子块结构 + 子召回后回挂父
- 在写入前验证：
  - 模型为 `Qwen/Qwen3-Embedding-8B`
  - 维度为 `1536`
- 同时写入：
  - Chroma
  - BM25 + jieba
- 支持单文档删除时同步删掉向量与 BM25 条目

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/indexing/test_index_modes.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/modules/indexing backend/app/clients/embedding_client.py backend/tests/indexing/test_index_modes.py
git commit -m "feat: add dual indexing modes"
```

---

### Task 6: 实现场景识别、权重配额与 HyBriD 检索

**Files:**
- Create: `backend/app/modules/retrieval/dto.py`
- Create: `backend/app/modules/retrieval/rewrite.py`
- Create: `backend/app/modules/retrieval/hybrid.py`
- Create: `backend/app/modules/retrieval/service.py`
- Create: `backend/tests/retrieval/test_scene_routing.py`
- Create: `backend/tests/retrieval/test_weighted_recall.py`
- Modify: `backend/app/api/v1/routes/query.py`

**Step 1: Write the failing test**

```python
def test_scene_3_uses_20_40_40_weights():
    scene = classify_scene(text="a", user_text="b", user_prompt="c")
    assert scene.name == "scene_3"
    assert scene.weights == {"text": 0.2, "user_text": 0.4, "user_prompt": 0.4}
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/retrieval/test_scene_routing.py backend/tests/retrieval/test_weighted_recall.py -v`
Expected: FAIL because scene classifier and weighted allocator do not exist.

**Step 3: Write minimal implementation**

- 实现场景 1/2/3/4 判定
- 每个输入源单独 rewrite
- 对每一路分别做：
  - 向量检索
  - BM25 检索
  - 融合
  - 断层截断
- 按 100 / 30-70 / 20-40-40 / 100 配额选候选
- 候选汇总后全局 rerank
- `POST /api/v1/query/retrieve` 返回中间结果用于调试

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/retrieval/test_scene_routing.py backend/tests/retrieval/test_weighted_recall.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/modules/retrieval backend/app/api/v1/routes/query.py backend/tests/retrieval/test_scene_routing.py backend/tests/retrieval/test_weighted_recall.py
git commit -m "feat: add weighted hybrid retrieval"
```

---

### Task 7: 实现 DeepSeek 问答编排与 SSE 引用输出

**Files:**
- Create: `backend/app/modules/qa/dto.py`
- Create: `backend/app/modules/qa/prompts.py`
- Create: `backend/app/modules/qa/streamer.py`
- Create: `backend/app/modules/qa/service.py`
- Create: `backend/tests/qa/test_sse_response.py`
- Modify: `backend/app/clients/llm_client.py`
- Modify: `backend/app/api/v1/routes/query.py`

**Step 1: Write the failing test**

```python
def test_sse_stream_emits_sources_before_done():
    events = list(build_sse_events(answer_chunks=["a"], sources=[{"source_id": 1}], total_tokens=10))
    assert any("event: sources" in event for event in events)
    assert events[-1].startswith("event: done")
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/qa/test_sse_response.py -v`
Expected: FAIL because SSE builder/QA service do not exist.

**Step 3: Write minimal implementation**

- 在 `prompts.py` 中定义场景系统提示词，特别是场景 1 的“灵感模式”约束
- 使用 DeepSeek 官方 API 生成回答
- SSE 固定输出：
  - `retrieval_start`
  - `retrieval_done`
  - `chunk`
  - `sources`
  - `done`
  - `error`
- 引用源至少返回：
  - `document_title`
  - `page`
  - `paragraph_id`
  - `snippet`

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/qa/test_sse_response.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/modules/qa backend/app/clients/llm_client.py backend/app/api/v1/routes/query.py backend/tests/qa/test_sse_response.py
git commit -m "feat: add deepseek citation-aware qa"
```

---

### Task 8: 连接 session、落库消息与来源，并替换旧路由依赖

**Files:**
- Create: `backend/tests/session/test_message_sources.py`
- Modify: `backend/app/modules/session/service.py`
- Modify: `backend/app/api/v1/routes/session.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/v1/router.py`
- Modify: `backend/app/models/query.py`

**Step 1: Write the failing test**

```python
def test_assistant_message_persists_sources_json(session_service):
    message = session_service.save_assistant_message("sess-1", "answer", [{"source_id": 1}])
    assert message.sources is not None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/session/test_message_sources.py -v`
Expected: FAIL because new session service path is not wired.

**Step 3: Write minimal implementation**

- 把聊天消息和来源写回 session 模块
- 让 query 路由使用新 `qa` / `retrieval` / `session` 模块
- 移除旧 `app/services/*rag*` 在路由层的直接依赖
- 保持旧 FastAPI 壳不变，但路由挂载改为新模块入口

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/session/test_message_sources.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/modules/session backend/app/api/v1/routes/session.py backend/app/main.py backend/app/api/v1/router.py backend/app/models/query.py backend/tests/session/test_message_sources.py
git commit -m "refactor: wire modular backend into api routes"
```

---

### Task 9: 建立端到端验证闭环

**Files:**
- Create: `backend/tests/e2e/test_import_retrieve_answer.py`
- Create: `backend/tests/e2e/test_delete_document.py`
- Modify: `backend/pyproject.toml`

**Step 1: Write the failing test**

```python
def test_scene_3_end_to_end_flow_returns_citations(client, fake_integrations):
    response = client.post("/api/v1/query/ask", json={
        "session_id": "sess-1",
        "text": "已写内容",
        "user_text": "圈选内容",
        "user_prompt": "请给我相关理论",
        "index_mode": "parent_child"
    })
    assert response.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/e2e/test_import_retrieve_answer.py backend/tests/e2e/test_delete_document.py -v`
Expected: FAIL because the full pipeline is not fully wired.

**Step 3: Write minimal implementation**

- 补测试夹具，mock 外部 API：
  - MinerU
  - SiliconFlow embedding/rerank
  - DeepSeek
- 跑通三条主链路：
  - 导入闭环
  - 场景 3 问答闭环
  - 删除闭环

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/e2e/test_import_retrieve_answer.py backend/tests/e2e/test_delete_document.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/tests/e2e backend/pyproject.toml
git commit -m "test: add backend e2e verification"
```

---

### Task 10: 进行全量验证并删除旧业务实现的调用入口

**Files:**
- Modify: `backend/app/services/cleaning_service.py`
- Modify: `backend/app/services/indexing_service.py`
- Modify: `backend/app/services/retrieval_service.py`
- Modify: `backend/app/services/qa_service_rag.py`
- Modify: `backend/app/services/query_rewrite_service.py`
- Modify: `backend/README.md` (if present later)

**Step 1: Write the failing test**

```python
def test_legacy_services_are_not_imported_by_api_routes():
    imports = collect_route_imports()
    assert "app.services.qa_service_rag" not in imports
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests -v`
Expected: FAIL because routes still depend on legacy modules or legacy files still expose active entrypoints.

**Step 3: Write minimal implementation**

- 删掉 API 路由对旧服务的直接依赖
- 将旧服务文件降级为兼容壳或明确废弃入口
- 确保新模块是唯一正式入口
- 跑完整测试与启动检查

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests -v && uv run python backend/main.py`
Expected: All tests PASS, service starts without configuration-structure errors.

**Step 5: Commit**

```bash
git add backend/app/services backend/tests
git commit -m "refactor: retire legacy backend service entrypoints"
```

---

## Final Verification Checklist

- [ ] `.env.example` 已提供 DeepSeek / SiliconFlow / MinerU 占位
- [ ] Embedding 模型固定 `Qwen/Qwen3-Embedding-8B`
- [ ] Embedding 维度固定 `1536`
- [ ] Reranker 固定 `Qwen/Qwen3-Reranker-8B`
- [ ] 仅 MinerU 作为 PDF 主链路
- [ ] `brute` 与 `parent_child` 两种索引模式可用
- [ ] 四种场景权重路由正确
- [ ] SSE 输出包含来源
- [ ] 删除文档会同时清掉 Chroma/BM25
- [ ] E2E 三条主链路通过

Plan complete and saved to `docs/plans/2026-03-25-mvp-backend-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - 我逐任务执行、每步校验、每块做代码复审

**2. Parallel Session (separate)** - 新会话用 `superpowers:executing-plans` 按计划批量推进

**Which approach?**
