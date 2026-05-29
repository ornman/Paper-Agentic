# 后端变更清单（自协作者代码同步后）

> 基准点：commit `4371615`（`chore: 同步协作者后端代码（origin/main）`）
> 截止点：commit `ebd510b`（`fix: retry 事件直接传 paper_id 而非 file_path`）
> 共 **10 个提交**涉及 `backend/`，变更 **21 个文件**（+278 / -1095 行）

---

## 一、新增功能

### 1. SSE 新事件：StatusEvent + DeltaEvent

**涉及文件：**
- `backend/app/agent_layer/contracts/sse_events.py` — 新增两个 Pydantic 模型
- `backend/app/agent_layer/orchestration/turn_runner.py` — 发射逻辑

**StatusEvent**（阶段指示）：
```
event: status
data: {"phase": "compacting|retrieving|reflecting|generating", "message": "...", "detail": {}}
```
- `compacting` — 对话历史压缩时
- `retrieving` — RAG 检索开始 / 补充检索时
- `reflecting` — 证据质量判断时
- `generating` — LLM 生成前

**DeltaEvent**（逐字流式输出）：
```
event: delta
data: {"text": "token片段"}
```
- LLM 每个 token 实时转发，前端实现打字机效果
- 替代旧的整块返回方式

### 2. PDF 元数据提取（新文件）

**新增文件：** `backend/app/data_layer/preprocessing/transformation/pdf_metadata.py`（88 行）

- 用 `pypdf` 从 PDF `/Info` 字典提取 title、authors、year
- 缺省时用文件名兜底
- 辅助函数：清理编码毛刺、解析 PDF 日期字符串

### 3. 导入重试接口

**涉及文件：** `backend/app/service_layer/api/library_routes.py`

```
POST /library/items/{item_id}/retry
```
流程：查原文件 → 删失败记录 → 重建导入任务 → 后台执行 → 返回 `{ task_id, status: "queued" }`

### 4. 导入进度百分比

**涉及文件：** `backend/app/service_layer/api/import_routes.py`

新增 `_STAGE_PERCENT` 映射：

| 阶段 | 百分比 |
|------|--------|
| starting | 8% |
| transforming | 25% |
| chunking | 60% |
| embedding | 75% |
| indexing | 90% |
| 完成 | 100% |

`GET /import/{task_id}/status` 现在返回 `percent` 字段。

### 5. Redis 初始化补全

**涉及文件：** `backend/app/service_layer/bootstrap/container.py`

`init()` 方法新增调用 `build_redis_runtime(self.settings)`，初始化：
- `redis_client`
- `conversation_window`
- `editor_context_store`
- `redis_health`

### 6. Redis 会话写入方法

**涉及文件：** `backend/app/agent_layer/session/redis_runtime.py`

`NullConversationWindowStore` 和 `RedisConversationWindowStore` 均新增：
```python
async def add_message(self, session_id: str, message) -> None
```

---

## 二、Bug 修复

| # | 问题 | 修复文件 | 修复内容 |
|---|------|----------|----------|
| 1 | MinerU Key 环境变量名不一致 | `mineru_adapter.py` + `settings.py` | 适配器改读 `MINERU_API_KEY`（fallback `MINERU_TOKEN`）；`settings.py` 启动时同步到 `os.environ` |
| 2 | library_items 表缺 authors/year 列导致 500 | `library_repo.py` | `init()` 加 `ALTER TABLE ADD COLUMN` 自动迁移 |
| 3 | 导入状态 `"completed"` 不写入完成时间 | `import_task_repo.py` | CASE 表达式加入 `'completed'` |
| 4 | 导入阶段仅推 SSE、未持久化到 DB | `import_routes.py` | `on_stage` 回调同时写 DB |
| 5 | 删除论文不删 library 记录 | `library_routes.py` | DELETE 端点补调 `library_repo.delete()` |
| 6 | 导入失败静默消失 | `library_routes.py` + `import_routes.py` | 失败时写入 `status="failed"` 的 LibraryItem |
| 7 | file_hash 计算了但未存储 | `import_routes.py` | `_run_import_with_progress()` 接收并存储 file_hash |
| 8 | 标题总是用文件名 | `import_routes.py` + `library_routes.py` | 调 `extract_pdf_metadata()` 优先用 PDF 内嵌标题 |
| 9 | library 路由用 `__dict__` 映射脆弱 | `library_routes.py` | 改为显式 `_item_to_out()` 映射函数 |
| 10 | 未处理异常无日志 | `exception_mapping.py` | 加 `exc_info=True` 日志记录 |

---

## 三、结构性删除

| 删除内容 | 行数 | 原因 |
|----------|------|------|
| `agent_layer/response/answer_generator.py` | -192 | 功能已被 TurnRunner 完全取代 |
| `data_layer/data_persistence/sqlite_runtime/` 下 4 个文件 | -446 | 与 `storage/sqlite_runtime/` 重复，保留规范路径 |
| 两份 `test_answer_generator.py` | -432 | 随 AnswerGenerator 一起删除 |

---

## 四、数据库 Schema 变更

### library_items 表新增列

```sql
ALTER TABLE library_items ADD COLUMN authors TEXT DEFAULT '';
ALTER TABLE library_items ADD COLUMN year TEXT DEFAULT '';
```

- 自动迁移：`library_repo.init()` 检测列是否存在，不存在则 ALTER
- 对应代码：`LibraryItem` dataclass、`LibraryItemOut` / `PaperItemOut` schema 均已同步

---

## 五、影响范围总结

| 层 | 变更 |
|----|------|
| Agent 层 | SSE 事件模型扩展（StatusEvent / DeltaEvent）、TurnRunner 阶段发射、Redis 会话写入 |
| 数据层 | PDF 元数据提取新模块、library_items schema 扩展、SQLite 自动迁移、重复代码清理 |
| 服务层 | 导入进度百分比、导入重试接口、导入失败写库、Redis 初始化、MinerU Key 同步 |
