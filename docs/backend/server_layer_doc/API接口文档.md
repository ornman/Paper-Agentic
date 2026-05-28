# API 接口文档

> Base URL: `http://127.0.0.1:8000/api/v1`
>
> 当前无认证，所有接口可直接访问。
>
> 本文档基于后端代码自动生成，是前端开发的唯一 API 契约。

---

## 目录

- [概述](#概述)
- [端点总览](#端点总览)
- [1. Health — 健康检查](#1-health--健康检查)
- [2. Library — 文献库管理](#2-library--文献库管理)
- [3. Papers — 论文管理（前端兼容）](#3-papers--论文管理前端兼容)
- [4. Import — 文档导入](#4-import--文档导入)
- [5. Conversations — 对话管理](#5-conversations--对话管理)
- [6. Assistant — 助手上下文](#6-assistant--助手上下文)
- [7. Query — Agent 查询](#7-query--agent-查询)
- [8. Models — 模型发现](#8-models--模型发现)
- [SSE 事件格式](#sse-事件格式)
- [数据模型](#数据模型)
- [错误码参考](#错误码参考)
- [前端集成指南](#前端集成指南)

---

## 概述

### 通用错误响应格式

所有 HTTP 错误（非 SSE）返回统一 JSON 格式：

```json
{"code": "error_code", "message": "人类可读的错误信息"}
```

`code` 取值见 [错误码参考](#错误码参考)。

### 文件格式限制

当前仅支持 **PDF** 格式。所有涉及文件上传/导入的端点都会校验文件后缀，非 PDF 文件将返回 400 错误。

---

## 端点总览

| 方法 | 路径 | 说明 | 标签 |
|------|------|------|------|
| GET | `/health` | 健康检查 | system |
| GET | `/library/items` | 列出文献库 | library |
| GET | `/library/items/{item_id}` | 获取单个文献 | library |
| DELETE | `/library/items/{item_id}` | 删除文献 | library |
| POST | `/library/import` | 按路径导入（服务端文件） | library |
| GET | `/library/import/{task_id}` | 查询导入任务状态 | library |
| GET | `/papers` | 列出论文（前端兼容） | papers |
| GET | `/papers/{paper_id}/open` | 下载论文 PDF | papers |
| DELETE | `/papers/{paper_id}` | 删除论文 | papers |
| POST | `/import/start` | 上传 PDF 并导入 | import |
| GET | `/import/status/{task_id}` | 查询导入状态 | import |
| GET | `/import/stream/{task_id}` | SSE 导入进度流 | import |
| GET | `/conversations` | 列出会话 | conversations |
| POST | `/conversations` | 新建会话 | conversations |
| GET | `/conversations/{session_id}` | 获取会话 | conversations |
| DELETE | `/conversations/{session_id}` | 删除会话 | conversations |
| GET | `/conversations/{session_id}/messages` | 获取消息历史 | conversations |
| POST | `/conversations/chat` | 发送消息（SSE 流式） | conversations |
| PUT | `/assistant/written-context` | 更新已写内容 | assistant |
| GET | `/assistant/written-context/{session_id}` | 获取已写内容 | assistant |
| PUT | `/assistant/selection` | 更新选中文本 | assistant |
| GET | `/assistant/selection/{session_id}` | 获取选中文本 | assistant |
| POST | `/assistant/polling/start` | 启动编辑器轮询 | assistant |
| POST | `/assistant/polling/stop` | 停止编辑器轮询 | assistant |
| POST | `/query` | Agent 查询（SSE 流式） | — |
| POST | `/models` | 模型发现 | models |

---

## 1. Health — 健康检查

### `GET /health`

返回后端各组件运行状态。

**响应** `200`:
```json
{
  "status": "ok",
  "components": {
    "chroma": {"status": "ok", "collection_count": 5, "total_vectors": 1234},
    "bm25": {"status": "ok", "doc_count": 1234},
    "redis": {"status": "ok", "detail": "connected"},
    "llm_config": {"status": "ok"},
    "embedding_config": {"status": "ok"}
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | `"ok"` / `"degraded"` / `"error"` |
| `components.chroma` | object | 向量库状态，含 `collection_count`、`total_vectors` |
| `components.bm25` | object | BM25 状态，含 `doc_count` |
| `components.redis` | object | Redis 状态，含 `detail` |
| `components.llm_config` | object | LLM 配置状态 |
| `components.embedding_config` | object | Embedding 配置状态 |

---

## 2. Library — 文献库管理

### `GET /library/items`

列出文献库中所有条目。

**响应** `200`: `LibraryItemOut[]`
```json
[
  {
    "library_item_id": "abc123",
    "kind": "paper",
    "title": "论文标题",
    "file_path": "/path/to/file.pdf",
    "file_hash": "a1b2c3d4e5f6",
    "authors": "张三",
    "file_size": 1048576,
    "chunk_count": 42,
    "total_pages": 15,
    "status": "completed",
    "import_time": "2026-05-28T10:00:00"
  }
]
```

### `GET /library/items/{item_id}`

获取单个文献条目。

**参数**: `item_id` (路径参数) — 文献 ID

**响应** `200`: `LibraryItemOut`（同上）

**错误** `404`:
```json
{"detail": "文献不存在"}
```

### `DELETE /library/items/{item_id}`

软删除文献（标记删除，不立即从索引移除）。

**参数**: `item_id` (路径参数)

**响应** `200`:
```json
{"status": "ok", "message": "已删除: 论文标题"}
```

**错误** `404`: `{"detail": "文献不存在"}`

### `POST /library/import`

按服务端文件路径导入文献（适用于文件已在服务器上的场景）。

**请求体**:
```json
{"file_path": "/data/uploads/paper.pdf"}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file_path` | string | 是 | 服务端 PDF 文件的绝对路径 |

**响应** `200`: `ImportResponse`
```json
{"task_id": "a1b2c3d4e5f6", "status": "queued", "message": "导入任务已创建"}
```

`status` 取值: `"queued"` | `"duplicate"`

**错误**:
- `400`: `{"detail": "文件不存在: /path/to/file"}`
- `400`: `{"detail": "仅支持 PDF 格式"}`

### `GET /library/import/{task_id}`

查询导入任务状态。

**参数**: `task_id` (路径参数)

**响应** `200`: `ImportTaskOut`
```json
{
  "task_id": "a1b2c3d4e5f6",
  "file_path": "/path/to/file.pdf",
  "status": "completed",
  "current_stage": "completed",
  "library_item_id": "abc123",
  "error_message": null,
  "created_at": "2026-05-28T10:00:00",
  "updated_at": "2026-05-28T10:01:30"
}
```

**错误** `404`: `{"detail": "导入任务不存在"}`

---

## 3. Papers — 论文管理（前端兼容）

> 前端专用路由，底层数据与 Library 共享。

### `GET /papers`

获取已导入论文列表。

**响应** `200`: `PaperListResponse`
```json
{
  "papers": [
    {
      "paper_id": "abc123",
      "title": "论文标题",
      "authors": "",
      "file_path": "/path/to/file.pdf",
      "file_hash": "a1b2c3d4e5f6",
      "chunk_count": 42,
      "total_pages": 15,
      "import_time": "2026-05-28T10:00:00",
      "status": "ready"
    }
  ]
}
```

### `GET /papers/{paper_id}/open`

下载/打开论文原始 PDF 文件。

**参数**: `paper_id` (路径参数)

**响应**: 文件流，`Content-Type: application/pdf`

**错误**:
- `404`: `{"detail": "论文不存在"}`
- `404`: `{"detail": "论文文件不存在"}`

### `DELETE /papers/{paper_id}`

删除论文（软删除）。

**参数**: `paper_id` (路径参数)

**响应** `200`:
```json
{"status": "ok", "message": "已删除: 论文标题"}
```

**错误** `404`: `{"detail": "论文不存在"}`

---

## 4. Import — 文档导入

### `POST /import/start`

上传 PDF 文件并开始异步导入。

**请求**: `multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | File | 是 | PDF 文件（仅支持 `.pdf`） |

**响应** `200`: `ImportStartResponse`
```json
{"task_id": "a1b2c3d4e5f6", "status": "queued"}
```

`status` 取值: `"queued"` | `"duplicate"`

**错误** `400`: `{"detail": "仅支持 PDF 格式"}`

**流程**:
1. 文件保存到 `uploads/` 目录
2. SHA256 哈希去重检查（重复文件返回 `duplicate`）
3. 创建异步导入任务
4. 返回 `task_id`，前端通过 SSE 或轮询获取进度

### `GET /import/status/{task_id}`

查询导入任务状态（轮询模式）。

**参数**: `task_id` (路径参数)

**响应** `200`: `ImportStatusResponse`
```json
{
  "task_id": "a1b2c3d4e5f6",
  "paper_id": "abc123",
  "status": "completed",
  "current_step": "completed",
  "error_msg": null,
  "file_name": "paper.pdf",
  "percent": null
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 任务 ID |
| `paper_id` | string? | 导入成功后生成的论文 ID |
| `status` | string | `"queued"` / `"running"` / `"completed"` / `"failed"` |
| `current_step` | string? | 当前处理阶段 |
| `error_msg` | string? | 失败时的错误信息 |
| `file_name` | string? | 原始文件名 |
| `percent` | float? | 进度百分比（预留，当前未实现） |

**错误** `404`: `{"detail": "导入任务不存在"}`

### `GET /import/stream/{task_id}`

SSE 流式推送导入进度（推荐方式）。

**参数**: `task_id` (路径参数)

**响应**: `text/event-stream`

```
event: progress
data: {"status": "running", "step": "starting", "paper_id": null}

event: progress
data: {"status": "running", "step": "transforming", "paper_id": null}

event: progress
data: {"status": "running", "step": "chunking", "paper_id": null}

event: progress
data: {"status": "completed", "step": "done", "paper_id": "abc123"}

event: progress
data: {"status": "done", "step": null, "paper_id": null}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | `"running"` / `"completed"` / `"failed"` / `"done"` / `"timeout"` |
| `step` | string? | 当前阶段名称 |
| `paper_id` | string? | 完成时的论文 ID |
| `error_msg` | string? | 失败时的错误信息 |

**连接行为**:
- 超时 300 秒无事件后发送 `{"status": "timeout"}` 并关闭
- `done` 事件为最终事件，之后连接关闭
- 响应头含 `Cache-Control: no-cache`、`X-Accel-Buffering: no`

---

## 5. Conversations — 对话管理

### `GET /conversations`

获取会话列表（最多 50 条）。

**响应** `200`: `ConversationSessionOut[]`
```json
[
  {
    "session_id": "a1b2c3d4",
    "title": "新对话",
    "created_at": "2026-05-28T10:00:00",
    "updated_at": "2026-05-28T10:05:00"
  }
]
```

### `POST /conversations`

新建会话。

**请求体**: 无（可选传空 JSON `{}`）

**响应** `200`: `ConversationSessionOut`（同上）

### `GET /conversations/{session_id}`

获取会话详情。

**参数**: `session_id` (路径参数)

**响应** `200`: `ConversationSessionOut`

**错误** `404`: `{"detail": "会话不存在"}`

### `DELETE /conversations/{session_id}`

删除会话及其所有消息。

**参数**: `session_id` (路径参数)

**响应** `200`:
```json
{"status": "ok", "message": "会话已删除"}
```

**错误** `404`: `{"detail": "会话不存在"}`

### `GET /conversations/{session_id}/messages`

获取会话的消息历史。

**参数**:
- `session_id` (路径参数)
- `limit` (查询参数, int, 默认 50) — 返回消息数量上限

**响应** `200`: `ConversationMessageOut[]`
```json
[
  {
    "session_id": "a1b2c3d4",
    "role": "user",
    "content": "这篇论文的主要贡献是什么？",
    "created_at": "2026-05-28T10:00:00",
    "sources_json": null
  },
  {
    "session_id": "a1b2c3d4",
    "role": "assistant",
    "content": "该论文的主要贡献是...",
    "created_at": "2026-05-28T10:00:05",
    "sources_json": "[{\"id\":\"src_1\",\"paper_id\":\"abc123\",...}]"
  }
]
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | string | 会话 ID |
| `role` | string | `"user"` / `"assistant"` |
| `content` | string | 消息内容 |
| `created_at` | string | ISO 时间戳 |
| `sources_json` | string? | assistant 消息的引用来源 JSON（`SourceCard[]` 序列化） |

### `POST /conversations/chat`

发送消息并获取 AI 回复（SSE 流式）。与 `/query` 共享同一套 Agent 编排引擎。

**请求体**: `ChatRequest`
```json
{
  "session_id": "",
  "message": "这篇论文的主要贡献是什么？",
  "paper_ids": ["paper1", "paper2"]
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `session_id` | string | 否 | `""` | 会话 ID；为空时自动创建新会话 |
| `message` | string | 是 | — | 用户消息 |
| `paper_ids` | string[]? | 否 | `null` | 限定检索的论文 ID 列表 |

**响应**: `text/event-stream`（详见 [SSE 事件格式](#sse-事件格式)）

**说明**: `session_id` 为空时自动生成 12 位 hex ID。请求中的 `enable_rag` 固定为 `true`，`thinking` 和 `reflection` 固定为 `false`。如需这些参数，请使用 `/query` 端点。

---

## 6. Assistant — 助手上下文

> 助手端点用于 WPS 插件与后端之间的编辑器上下文同步。部分功能依赖 Redis，Redis 不可用时返回降级响应。

### `PUT /assistant/written-context`

更新用户已写内容（WPS 插件主动推送）。

**请求体**: `WrittenContextUpdate`
```json
{"session_id": "xxx", "content": "用户正在编辑的内容..."}
```

**响应** `200`:
```json
{"status": "ok", "session_id": "xxx"}
```

Redis 不可用时返回降级响应（非错误）:
```json
{"status": "degraded", "message": "Redis 不可用，上下文未持久化"}
```

### `GET /assistant/written-context/{session_id}`

获取当前已写内容。

**参数**: `session_id` (路径参数)

**响应** `200`: `ContextState`
```json
{"session_id": "xxx", "written_context": "用户已写内容...", "selection": ""}
```

### `PUT /assistant/selection`

更新用户选中的文本。

**请求体**: `EditorSelectionUpdate`
```json
{"session_id": "xxx", "selection": "用户选中的文本..."}
```

**响应** `200`: 同 `written-context`，支持降级。

### `GET /assistant/selection/{session_id}`

获取当前选中文本。

**参数**: `session_id` (路径参数)

**响应** `200`: `ContextState`
```json
{"session_id": "xxx", "written_context": "", "selection": "选中的文本..."}
```

### `POST /assistant/polling/start`

启动后端轮询编辑器内容（后端主动拉取模式，当前为占位实现）。

**请求体**: `PollingStartRequest`
```json
{"session_id": "xxx", "interval": 5}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `session_id` | string | 是 | — | 目标会话 ID |
| `interval` | int | 否 | `5` | 轮询间隔（秒），范围 1-60 |

**响应** `200`:
```json
{"status": "ok", "message": "轮询已启动，间隔 5s"}
```

**错误** `503`: `{"detail": "编辑器上下文存储不可用（Redis 未连接）"}`

### `POST /assistant/polling/stop`

停止编辑器轮询。

**响应** `200`:
```json
{"status": "ok", "message": "轮询已停止"}
```

**错误** `503`: `{"detail": "编辑器上下文存储不可用（Redis 未连接）"}`

---

## 7. Query — Agent 查询

### `POST /query`

Agent 主链入口：提问 → 检索 → 生成 → 流式返回。

**请求体**: `AskRequest`
```json
{
  "session_id": "xxx",
  "prompt": "这篇论文的主要贡献是什么？",
  "selection": "可选：用户选中的文本",
  "draft": "可选：用户当前草稿",
  "paper_ids": ["paper1", "paper2"],
  "enable_rag": true,
  "model": null,
  "thinking": false,
  "reflection": false
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `session_id` | string | 是 | — | 会话 ID |
| `prompt` | string | 是 | — | 用户提问 |
| `selection` | string? | 否 | `null` | 用户在编辑器中选中的文本 |
| `draft` | string? | 否 | `null` | 用户当前草稿内容 |
| `paper_ids` | string[]? | 否 | `null` | 限定检索的论文 ID 列表 |
| `enable_rag` | bool | 否 | `true` | 是否启用 RAG 检索 |
| `model` | string? | 否 | `null` | 指定模型（默认用配置的模型） |
| `thinking` | bool | 否 | `false` | 是否启用思考模式 |
| `reflection` | bool | 否 | `false` | 是否启用反思（自动判断检索质量并重试） |

**响应**: `text/event-stream`（详见 [SSE 事件格式](#sse-事件格式)）

**与 `/conversations/chat` 的区别**:
- `/query` 支持全部参数（`selection`、`draft`、`model`、`thinking`、`reflection`）
- `/conversations/chat` 简化版，`enable_rag=true`，其余高级参数固定为默认值
- 两者共享同一个 `TurnRunner` 引擎，SSE 事件格式完全一致

---

## 8. Models — 模型发现

### `POST /models`

从 OpenAI 兼容的 API 获取可用模型列表。

**请求体**: `ModelDiscoveryRequest`
```json
{"api_key": "sk-xxx", "api_url": "https://api.openai.com/v1"}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `api_key` | string | 是 | API 密钥 |
| `api_url` | string | 是 | API 基础 URL（OpenAI 兼容） |

**响应** `200`: `ModelListResponse`
```json
{
  "models": [
    {"id": "gpt-4", "name": "gpt-4", "provider": "openai", "support_thinking": null}
  ]
}
```

**错误** `502`:
```json
{"detail": "模型列表获取失败: Connection error..."}
```

---

## SSE 事件格式

`POST /query` 和 `POST /conversations/chat` 返回 `text/event-stream`。

事件格式遵循 SSE 规范：`event: <type>\ndata: <JSON>\n\n`

### 事件类型总览

| 事件 | 说明 | 触发条件 |
|------|------|----------|
| `metadata` | 请求元信息 | 每次请求必发（首个事件） |
| `reflection` | 检索反思 | `reflection: true` 时触发 |
| `thinking` | 思考过程 | `thinking: true` 时触发 |
| `block` | 内容块 | LLM 生成过程中逐块发送 |
| `sources` | 引用来源 | 有检索结果时发送 |
| `tool_round` | 工具调用 | LLM 决定调用工具时触发 |
| `done` | 流结束 | 每次请求必发（最终事件） |
| `error` | 错误 | 发生错误时触发 |

### `metadata` — 请求元信息（首个事件）

```json
{
  "request_id": "abc123",
  "session_id": "xxx",
  "used_inputs": {"prompt": 1.0, "selection": 0.0, "written_context": 0.0, "rag_evidence": 0.0},
  "context_tokens": 150,
  "remaining_tokens": 31850,
  "remaining_ratio": 0.9953,
  "retrieval_planned": true,
  "degraded_flags": [],
  "cache_mode": "memory"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `request_id` | string | 请求唯一 ID |
| `session_id` | string | 会话 ID |
| `used_inputs` | object | 各输入源权重（0.0-1.0） |
| `context_tokens` | int | 输入上下文估算 token 数 |
| `remaining_tokens` | int | 剩余可用 token |
| `remaining_ratio` | float | 剩余比例（0.0-1.0） |
| `retrieval_planned` | bool | 是否计划检索 |
| `degraded_flags` | string[] | 降级标志列表 |
| `cache_mode` | string | 缓存模式（`"memory"`） |

### `reflection` — 检索反思

`reflection: true` 时触发，最多 3 轮。

```json
{"round": 1, "verdict": "insufficient", "reason": "检索结果中缺少关于方法论的具体描述"}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `round` | int | 反思轮次（1-3） |
| `verdict` | string | 判定结果 |
| `reason` | string | 判定原因 |

`verdict` 取值:
- `"sufficient"` — 检索结果足够支撑回答
- `"insufficient"` — 检索结果不足，将扩大 topk 重试
- `"off_track"` — 检索方向偏离，将修正 query 重试
- `"conflicting"` — 检索结果矛盾，将修正 query 重试

### `thinking` — 思考过程

`thinking: true` 时触发。

```json
{"text": "让我分析这篇论文...", "time_ms": 1234}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `text` | string | 思考文本 |
| `time_ms` | int | 思考耗时（毫秒） |

### `block` — 内容块

LLM 生成过程中逐块发送。通过 `type` 字段区分块类型。

详见 [ContentBlock](#contentblock)。

### `sources` — 引用来源

有检索结果时发送。

```json
[
  {
    "id": "src_1",
    "paper_id": "abc123",
    "title": "论文标题",
    "page": 3,
    "section": "Abstract",
    "file_path": "/data/papers/abc123/paper.pdf",
    "local_path": "/data/papers/abc123/paper.pdf",
    "content": "相关段落文本（截断至 220 字符）...",
    "import_time": "2026-05-28T10:00:00"
  }
]
```

详见 [SourceCard](#sourcecard)。

### `tool_round` — 工具调用

LLM 决定调用工具时触发（最多 5 轮）。

```json
{"round": 1, "tool_name": "search_papers", "status": "success"}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `round` | int | 工具调用轮次 |
| `tool_name` | string | 工具名称 |
| `status` | string | 调用状态 |

### `done` — 流结束

每次请求必发，表示流结束。

```json
{}
```

### `error` — 错误

发生错误时触发。

```json
{
  "message": "检索失败，请稍后重试",
  "code": "retrieval_error",
  "stage": "retrieval",
  "retryable": true,
  "degraded": false,
  "suggested_action": "请检查网络连接后重试"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `message` | string | 是 | 错误信息 |
| `code` | string? | 否 | 错误代码 |
| `stage` | string? | 否 | 出错阶段（`"retrieval"` / `"generation"` 等） |
| `retryable` | bool? | 否 | 是否可重试 |
| `degraded` | bool? | 否 | 是否降级运行 |
| `suggested_action` | string? | 否 | 建议的用户操作 |

---

## 数据模型

### AskRequest

Agent 查询请求体（`/query` 端点使用）。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `session_id` | string | 是 | — | 会话 ID |
| `prompt` | string | 是 | — | 用户提问 |
| `selection` | string? | 否 | `null` | 选中文本 |
| `draft` | string? | 否 | `null` | 草稿内容 |
| `paper_ids` | string[]? | 否 | `null` | 限定检索论文 |
| `enable_rag` | bool | 否 | `true` | 启用 RAG |
| `model` | string? | 否 | `null` | 指定模型 |
| `thinking` | bool | 否 | `false` | 思考模式 |
| `reflection` | bool | 否 | `false` | 反思模式 |

### ChatRequest

对话请求体（`/conversations/chat` 端点使用）。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `session_id` | string | 否 | `""` | 会话 ID，为空自动创建 |
| `message` | string | 是 | — | 用户消息 |
| `paper_ids` | string[]? | 否 | `null` | 限定检索论文 |

### ContentBlock

内容块（`block` SSE 事件的数据），通过 `type` 字段区分。共 7 种变体：

#### `paragraph` — 段落

```json
{"type": "paragraph", "text": "论文的主要贡献是...", "citations": [{"sourceId": "src_1"}]}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `text` | string | 段落文本 |
| `citations` | `BlockCitation[]?` | 引用列表 |

#### `heading` — 标题

```json
{"type": "heading", "level": 2, "text": "研究方法"}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `level` | int | 标题级别（1-4） |
| `text` | string | 标题文本 |

#### `list` — 列表

```json
{"type": "list", "ordered": true, "items": ["第一点", "第二点"]}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `ordered` | bool | 是否有序列表 |
| `items` | string[] | 列表项 |

#### `citation_block` — 引用块

```json
{"type": "citation_block", "text": "根据文献 [1]...", "sourceIds": ["src_1", "src_2"]}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `text` | string | 引用文本 |
| `sourceIds` | string[] | 来源 ID 列表 |

#### `table` — 表格

```json
{"type": "table", "headers": ["方法", "准确率"], "rows": [["BERT", "92.5%"], ["GPT", "95.1%"]]}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `headers` | string[] | 表头 |
| `rows` | string[][] | 表格数据 |

#### `code` — 代码块

```json
{"type": "code", "language": "python", "code": "print('hello')"}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `language` | string | 编程语言 |
| `code` | string | 代码内容 |

#### `divider` — 分隔线

```json
{"type": "divider"}
```

无额外字段。

#### BlockCitation

`paragraph` 块中的引用对象。

| 字段 | 类型 | 说明 |
|------|------|------|
| `sourceId` | string | 来源 ID（对应 SourceCard.id） |

### SourceCard

引用来源卡片（`sources` SSE 事件的数据）。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 来源唯一 ID（如 `"src_1"`） |
| `paper_id` | string? | 否 | 关联的论文 ID |
| `title` | string | 是 | 来源标题（论文标题或章节名） |
| `page` | int? | 否 | 页码 |
| `section` | string? | 否 | 章节名 |
| `file_path` | string? | 否 | 文件路径 |
| `local_path` | string? | 否 | 本地文件路径 |
| `content` | string? | 否 | 相关文本片段（截断至 220 字符） |
| `import_time` | string? | 否 | 导入时间（ISO 格式） |

### LibraryItemOut

文献库条目。

| 字段 | 类型 | 说明 |
|------|------|------|
| `library_item_id` | string | 文献 ID |
| `kind` | string | 类型（`"paper"`） |
| `title` | string | 标题 |
| `file_path` | string | 文件路径 |
| `file_hash` | string | 文件哈希（SHA256 前 16 位） |
| `authors` | string | 作者 |
| `file_size` | int? | 文件大小（字节） |
| `chunk_count` | int | 切分块数 |
| `total_pages` | int? | 总页数 |
| `status` | string | 状态 |
| `import_time` | string | 导入时间 |

### PaperItemOut

论文条目（前端兼容）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `paper_id` | string | 论文 ID |
| `title` | string | 标题 |
| `authors` | string | 作者 |
| `file_path` | string | 文件路径 |
| `file_hash` | string | 文件哈希 |
| `chunk_count` | int | 切分块数 |
| `total_pages` | int | 总页数 |
| `import_time` | string | 导入时间 |
| `status` | string | 状态（`"ready"`） |

### ConversationSessionOut

会话信息。

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | string | 会话 ID |
| `title` | string | 会话标题 |
| `created_at` | string | 创建时间 |
| `updated_at` | string | 更新时间 |

### ConversationMessageOut

消息记录。

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | string | 会话 ID |
| `role` | string | `"user"` / `"assistant"` |
| `content` | string | 消息内容 |
| `created_at` | string | 创建时间 |
| `sources_json` | string? | 引用来源 JSON（仅 assistant 消息） |

### ContextState

编辑器上下文状态。

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | string | 会话 ID |
| `written_context` | string | 已写内容 |
| `selection` | string | 选中文本 |

### ModelInfo

模型信息。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 模型 ID |
| `name` | string | 模型名称 |
| `provider` | string? | 提供商 |
| `support_thinking` | bool? | 是否支持思考模式 |

---

## 错误码参考

### HTTP 状态码

| 状态码 | 说明 | 常见场景 |
|--------|------|----------|
| 200 | 成功 | — |
| 400 | 请求参数错误 | 文件格式不支持、参数校验失败 |
| 404 | 资源不存在 | 论文/会话/任务不存在 |
| 409 | 冲突 | 重复导入 |
| 422 | 请求体校验失败 | Pydantic 字段类型错误 |
| 500 | 服务器内部错误 | 未捕获异常 |
| 502 | 外部服务调用失败 | 模型发现 API 不可达 |
| 503 | 服务不可用 | Redis 未连接 |

### 业务错误码（`code` 字段）

| code | HTTP 状态 | 说明 |
|------|-----------|------|
| `validation_error` | 400 | 参数校验失败 |
| `domain_error` | 400 | 业务逻辑错误 |
| `not_found` | 404 | 资源不存在 |
| `conflict` | 409 | 资源冲突 |
| `service_unavailable` | 503 | 服务不可用 |
| `internal_error` | 500 | 内部错误（消息固定为 `"内部错误"`） |

---

## 前端集成指南

### SSE 连接方式

```typescript
// 方式一：EventSource（仅 GET，适用于导入进度）
const es = new EventSource('/api/v1/import/stream/{task_id}');
es.addEventListener('progress', (e) => {
  const data = JSON.parse(e.data);
  if (data.status === 'done' || data.status === 'completed') {
    es.close();
  }
});

// 方式二：fetch + ReadableStream（适用于 POST 请求）
async function queryChat(sessionId: string, message: string) {
  const resp = await fetch('/api/v1/query', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({session_id: sessionId, prompt: message}),
  });

  const reader = resp.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, {stream: true});

    // 按 SSE 帧分割
    const frames = buffer.split('\n\n');
    buffer = frames.pop()!; // 最后一个可能不完整

    for (const frame of frames) {
      const eventMatch = frame.match(/^event: (.+)$/m);
      const dataMatch = frame.match(/^data: (.+)$/m);
      if (!eventMatch || !dataMatch) continue;

      const eventType = eventMatch[1];
      const data = JSON.parse(dataMatch[1]);
      handleEvent(eventType, data);
    }
  }
}
```

### 事件处理顺序

1. `metadata` — 初始化 UI（显示 token 用量、是否检索等）
2. `reflection` — 显示检索质量评估（可选）
3. `thinking` — 显示思考过程（可选）
4. `block` × N — 逐块渲染内容（核心）
5. `sources` — 显示引用来源面板
6. `done` — 完成，清理状态

`error` 可在任意时刻出现，需随时监听。

### 前端 WPS 插件集成流程

```
1. 用户选中文本 → PUT /assistant/selection
2. 用户开始提问 → POST /query（含 selection）
3. 前端监听 SSE 事件流
4. block 事件 → 逐块渲染到侧边栏
5. sources 事件 → 显示引用面板
6. done 事件 → 完成
```
