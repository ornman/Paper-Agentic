# API 接口设计 - 论文助手（重构版 v2.0）

> 版本: v2.0
> 更新日期: 2026-04-18
> 对应架构: [02-设计/架构/架构设计.md](../架构/架构设计.md)

---

## 1. 概述

### 1.1 通信协议

| 类型 | 协议 | 用途 |
|------|------|------|
| 常规请求 | HTTP REST (JSON) | 导入、管理、历史查询 |
| 流式响应 | SSE (Server-Sent Events) | 问答生成、导入进度 |

### 1.2 通用响应格式

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

错误响应：

```json
{
  "code": 4001,
  "message": "论文不存在",
  "data": null
}
```

### 1.3 错误码规范

| 范围 | 含义 |
|------|------|
| 0 | 成功 |
| 1000-1999 | 客户端错误（参数、权限） |
| 2000-2999 | 业务错误（论文不存在、导入失败） |
| 3000-3999 | 外部服务错误（MinerU、Kimi、Embedding） |
| 5000-5999 | 服务端内部错误 |

---

## 2. 数据导入接口

### 2.1 POST /api/v1/import/start

启动 PDF 导入工作流（`/start` 指令对应的后端接口）。

**请求**:

```json
{
  "file_path": "D:\\papers\\xxx.pdf",
  "chunk_strategy": "semantic"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file_path | string | 是 | 本地 PDF 绝对路径 |
| chunk_strategy | string | 否 | 切分策略: `semantic`(默认) / `brute_force` |

**响应**:

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "import_1713440000_abc",
    "status": "processing"
  }
}
```

**处理流程**:
1. 校验文件存在性 + 格式（仅 PDF）
2. 计算 file_hash，检查是否已导入（去重）
3. 异步执行: MinerU 解析 → 噪音过滤 → 图片描述 → 语义切块 → Embedding → 入库
4. 通过 SSE 推送进度

**错误码**:

| code | 说明 |
|------|------|
| 1001 | 文件路径为空 |
| 1002 | 文件不存在或非 PDF |
| 2001 | 该论文已导入（返回已有 paper_id） |

### 2.2 GET /api/v1/import/status/{task_id}

查询导入任务状态。

**响应**:

```json
{
  "code": 0,
  "data": {
    "task_id": "import_1713440000_abc",
    "status": "processing",
    "progress": {
      "current_step": "embedding",
      "steps": [
        { "name": "parse", "status": "completed" },
        { "name": "clean", "status": "completed" },
        { "name": "chunk", "status": "completed" },
        { "name": "embedding", "status": "processing", "progress": 60 },
        { "name": "store", "status": "pending" }
      ]
    },
    "paper_id": "paper_1713440000"
  }
}
```

| status 值 | 说明 |
|-----------|------|
| pending | 排队中 |
| processing | 处理中 |
| completed | 完成 |
| failed | 失败（附带 error_msg） |

### 2.3 SSE /api/v1/import/stream/{task_id}

SSE 流式推送导入进度（可选，替代轮询 status）。

**事件格式**:

```
event: progress
data: {"step": "embedding", "progress": 60}

event: completed
data: {"paper_id": "paper_1713440000", "chunk_count": 45}

event: error
data: {"step": "embedding", "message": "硅基流动 API 超时，正在降级重试..."}
```

---

## 3. 检索问答接口

### 3.1 POST /api/v1/query

核心问答接口，支持四种模式。SSE 流式返回。

**请求**:

```json
{
  "session_id": "sess_1713440000",
  "user_prompt": "Transformer在NLP中的应用",
  "selection": "cross-attention mechanism in machine translation",
  "draft_context": null,
  "intent_override": null
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| session_id | string | 是 | 会话 ID（关联 Redis 对话历史） |
| user_prompt | string | 否 | 用户输入的提示词 |
| selection | string | 否 | 用户圈选的文本 |
| draft_context | string | 否 | 前端轮询的已写内容（由后端缓存，也可前端传） |
| intent_override | string | 否 | 强制指定 intent（调试用） |

**模式自动识别**:

| 有 prompt | 有 selection | 有 draft | → 模式 |
|-----------|-------------|----------|--------|
| ✅ | ❌ | ❌ | 纯提问 |
| ❌ | ❌ | ✅ | 纯续写 |
| ❌ | ✅ | ✅ | 圈选辅助 |
| ✅ | ✅ | ✅ | 全量 |

**SSE 响应**:

```
event: metadata
data: {
  "query_schema": {
    "intent": {"task": "ask"},
    "sources": [
      {
        "type": "prompt",
        "dense_query": "Transformer architecture applications...",
        "sparse_query": ["Transformer", "NLP", ...],
        "weight_hint": 0.6
      }
    ],
    "retrieval_stats": {
      "dense_hits": 12,
      "sparse_hits": 15,
      "fused_count": 10,
      "sources": [
        {"paper_id": "xxx", "title": "...", "page": 12, "score": 0.95}
      ]
    }
  }
}

event: token
data: {"content": "Transformer"}

event: token
data: {"content": "在自然语言处理"}

event: token
data: {"content": "领域的应用非常广泛..."}

event: sources
data: {
  "sources": [
    {
      "paper_id": "paper_1713440000",
      "title": "Attention Is All You Need",
      "page": 3,
      "section": "3.2 Applications",
      "chunk_index": 8,
      "local_path": "D:\\papers\\xxx.pdf"
    }
  ]
}

event: done
data: {"usage": {"prompt_tokens": 1200, "completion_tokens": 450}}
```

### 3.2 POST /api/v1/query/preview

预览 Query 改写结果（调试/开发用），不调用 LLM。

**请求**: 同 `/query`

**响应**:

```json
{
  "code": 0,
  "data": {
    "intent": { "task": "ask", "need_external_retrieval": true },
    "sources": [
      {
        "type": "prompt",
        "raw": "Transformer在NLP中的应用",
        "dense_query": "Transformer architecture applications in natural language processing",
        "sparse_query": ["Transformer", "NLP", "text classification", "machine translation"],
        "weight_hint": 0.6
      }
    ],
    "fusion": {
      "method": "weighted_rrf",
      "per_source_cap": 10,
      "per_doc_cap": 2
    }
  }
}
```

---

## 4. 文献库管理接口

### 4.1 GET /api/v1/papers

获取论文列表。

**查询参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| page | int | 页码（默认 1） |
| limit | int | 每页条数（默认 20） |
| keyword | string | 按标题/作者搜索 |

**响应**:

```json
{
  "code": 0,
  "data": {
    "total": 15,
    "page": 1,
    "limit": 20,
    "items": [
      {
        "paper_id": "paper_1713440000",
        "title": "Attention Is All You Need",
        "authors": "Vaswani et al.",
        "chunk_count": 45,
        "import_time": "2026-04-18T10:00:00",
        "file_path": "D:\\papers\\xxx.pdf"
      }
    ]
  }
}
```

### 4.2 GET /api/v1/papers/{paper_id}

获取单篇论文详情（含元数据）。

**响应**:

```json
{
  "code": 0,
  "data": {
    "paper_id": "paper_1713440000",
    "title": "Attention Is All You Need",
    "authors": "Vaswani et al.",
    "file_path": "D:\\papers\\xxx.pdf",
    "chunk_count": 45,
    "import_time": "2026-04-18T10:00:00",
    "metadata": {
      "sections": ["Introduction", "Background", "Model Architecture", ...],
      "image_count": 5,
      "total_pages": 12
    }
  }
}
```

### 4.3 DELETE /api/v1/papers/{paper_id}

删除论文及其所有向量数据。

**响应**:

```json
{
  "code": 0,
  "message": "已删除，共清理 45 个向量块"
}
```

**内部操作**:
1. Zvec: `delete_by_filter("paper_id == 'xxx'")`
2. SQLite: DELETE FROM papers WHERE paper_id = 'xxx'
3. 返回删除的 chunk 数量

---

## 5. 对话管理接口

### 5.1 GET /api/v1/conversations

获取会话列表。

**响应**:

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "session_id": "sess_1713440000",
        "created_at": "2026-04-18T10:00:00",
        "message_count": 8,
        "last_message": "Transformer在NLP中..."
      }
    ]
  }
}
```

### 5.2 GET /api/v1/conversations/{session_id}

获取会话历史。

**查询参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| limit | int | 最近 N 条消息（默认 50） |

**响应**:

```json
{
  "code": 0,
  "data": {
    "session_id": "sess_1713440000",
    "messages": [
      {
        "role": "user",
        "content": "Transformer在NLP中的应用",
        "timestamp": 1713440000,
        "sources": null
      },
      {
        "role": "assistant",
        "content": "Transformer在自然语言处理领域的应用非常广泛...",
        "timestamp": 1713440010,
        "sources": [
          {"paper_id": "xxx", "title": "...", "page": 3, "section": "3.2"}
        ]
      }
    ]
  }
}
```

### 5.3 DELETE /api/v1/conversations/{session_id}

删除会话及其 Redis 缓存。

### 5.4 POST /api/v1/conversations

创建新会话。

**响应**:

```json
{
  "code": 0,
  "data": {
    "session_id": "sess_1713440050"
  }
}
```

---

## 6. WPS 轮询接口

### 6.1 POST /api/v1/poll/sync

同步 WPS 文档轮询内容到后端缓存。

**请求**:

```json
{
  "session_id": "sess_1713440000",
  "content": "用户当前文档中已写的全部文本内容..."
}
```

**响应**:

```json
{
  "code": 0,
  "data": {
    "cached": true,
    "content_length": 2400
  }
}
```

**说明**: 前端每 5 秒调用一次，后端将内容缓存到该 session 的临时存储中。WPS 关闭时前端停止轮询，后端 TTL 自动清理。

---

## 7. 系统接口

### 7.1 GET /api/v1/health

健康检查。

**响应**:

```json
{
  "code": 0,
  "data": {
    "status": "healthy",
    "components": {
      "zvec": "ok",
      "sqlite": "ok",
      "redis": "ok",
      "kimi_api": "ok"
    },
    "stats": {
      "paper_count": 15,
      "chunk_count": 675,
      "active_sessions": 2
    }
  }
}
```

### 7.2 GET /api/v1/config

获取用户可配参数（不暴露敏感 Key）。

**响应**:

```json
{
  "code": 0,
  "data": {
    "models": {
      "llm": "K2.6-code-preview",
      "embedding": "Qwen/Qwen3-Embedding-8B",
      "embedding_dimensions": 1536
    },
    "retrieval": {
      "dense_topk": 15,
      "sparse_topk": 15,
      "fusion_topk": 15,
      "per_source_cap": 10,
      "per_doc_cap": 2
    },
    "chunking": {
      "max_context": 32000,
      "target_size": 24000,
      "overlap_buffer": 8000
    }
  }
}
```

---

## 8. 接口汇总

| 方法 | 路径 | 说明 | SSE |
|------|------|------|-----|
| POST | /api/v1/import/start | 启动 PDF 导入 | ❌ |
| GET | /api/v1/import/status/{task_id} | 查询导入状态 | ❌ |
| SSE | /api/v1/import/stream/{task_id} | 导入进度流 | ✅ |
| POST | /api/v1/query | 核心问答 | ✅ |
| POST | /api/v1/query/preview | 预览 Query 改写 | ❌ |
| GET | /api/v1/papers | 论文列表 | ❌ |
| GET | /api/v1/papers/{paper_id} | 论文详情 | ❌ |
| DELETE | /api/v1/papers/{paper_id} | 删除论文 | ❌ |
| GET | /api/v1/conversations | 会话列表 | ❌ |
| POST | /api/v1/conversations | 创建会话 | ❌ |
| GET | /api/v1/conversations/{session_id} | 会话历史 | ❌ |
| DELETE | /api/v1/conversations/{session_id} | 删除会话 | ❌ |
| POST | /api/v1/poll/sync | WPS 轮询同步 | ❌ |
| GET | /api/v1/health | 健康检查 | ❌ |
| GET | /api/v1/config | 配置信息 | ❌ |
