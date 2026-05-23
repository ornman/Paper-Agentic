# V1 API 接口文档

> 基于 routes/ 实际代码，2026-04-19
> Base URL: `/api/v1`

---

## 健康检查

### GET /health

返回各组件状态。

**响应**:
```json
{
  "status": "healthy",
  "components": {
    "sqlite": "ok",
    "zvec": "ok",
    "redis": "ok"
  }
}
```

Redis 不可用时降级为 `"redis": "unavailable"`，整体 status 仍为 `healthy`。

---

## 论文导入

### POST /import/start

上传 PDF 并启动异步导入任务。

**请求**: `multipart/form-data`
- `file`: PDF 文件

**响应**:
```json
{
  "task_id": "uuid-string",
  "status": "started",
  "message": "导入任务已启动"
}
```

导入管道 6 阶段: MinerU解析 → VLM图片描述 → 清洗 → 切块 → Embedding → 存储。

### GET /import/status/{task_id}

查询导入任务状态。

**响应**:
```json
{
  "task_id": "uuid-string",
  "status": "processing",
  "stage": "embedding",
  "message": "正在生成向量...",
  "paper_id": "paper_xxx"
}
```

**status 取值**: `started`, `processing`, `completed`, `failed`

### GET /import/stream/{task_id}

SSE 实时进度流。

**事件格式**:
```
event: progress
data: {"stage": "cleaning", "message": "正在清洗..."}

event: progress
data: {"stage": "embedding", "message": "正在生成向量..."}

event: complete
data: {"paper_id": "paper_xxx", "chunk_count": 96}

event: error
data: {"message": "错误描述"}
```

---

## 问答

### POST /query

SSE 流式问答。支持四种模式。

**请求**:
```json
{
  "session_id": "sess_xxx",
  "prompt": "VR技术在博物馆中的应用有哪些？",
  "selection": "圈选的文本",
  "draft": "草稿文本",
  "paper_ids": ["paper_001", "paper_002"]
}
```

**四种模式**（按字段组合自动识别）:

| 模式 | prompt | selection | draft | 权重 |
|------|--------|-----------|-------|------|
| 纯提问 | ✓ | | | prompt 100% |
| 圈选辅助 | ✓ | ✓ | ✓ | draft 30% + sel 70% |
| 纯续写 | | | ✓ | draft 100% |
| 全量 | ✓ | ✓ | ✓ | draft 20% + sel 30% + prompt 50% |

**SSE 事件**:
```
event: metadata
data: {"sources": [{"paper_id":"p1","title":"...","page":3}]}

event: chunk
data: {"content": "根据文献..."}

event: done
data: {}

event: error
data: {"message": "错误描述"}
```

---

## 论文管理

### GET /papers

列出所有已导入论文。

**响应**:
```json
{
  "papers": [
    {
      "paper_id": "paper_xxx",
      "title": "论文标题",
      "authors": "",
      "file_path": "/path/to/pdf",
      "chunk_count": 96,
      "status": "completed",
      "import_time": "2026-04-19T12:00:00"
    }
  ],
  "total": 1
}
```

### DELETE /papers/{paper_id}

删除论文及其所有数据（SQLite + Zvec + BM25）。

**响应**:
```json
{
  "message": "论文已删除",
  "paper_id": "paper_xxx"
}
```

---

## 对话历史

### GET /conversations/{session_id}

获取会话的对话历史。

**响应**:
```json
{
  "session_id": "sess_xxx",
  "messages": [
    {"role": "user", "content": "VR技术有哪些应用？"},
    {"role": "assistant", "content": "根据文献..."}
  ]
}
```

### DELETE /conversations/{session_id}

清除会话历史。

**响应**:
```json
{
  "message": "对话历史已清除"
}
```

---

## 轮询同步

### POST /poll/sync

WPS 插件定期同步当前文档内容（用于后续检索）。

**请求**:
```json
{
  "session_id": "sess_xxx",
  "content": "当前文档的文本内容"
}
```

**响应**:
```json
{
  "message": "同步成功"
}
```

内容缓存到 Redis，TTL 1 小时，问答时可检索利用。
