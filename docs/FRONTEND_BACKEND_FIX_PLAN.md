# 前后端连通性修复计划

## Context

审计发现 3 个阻断级前端-后端对接 bug：
1. `fetchPapers()` 字段映射错误——`paper_id` 恒为 `undefined`，导致文献管理面板完全不可用
2. `retryImport()` 调用的后端端点不存在，导致重试导入功能 404
3. 会话历史未在页面挂载时自动加载，刷新后无法恢复上次会话

## 修复范围

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `frontend/src/services/library-api.ts` | 修正 `fetchPapers()` 的端点调用和字段映射 |
| `frontend/src/services/library-api.ts` | 修正 `deletePaper()` 使用正确的 API 路径 |
| `frontend/src/services/library-api.ts` | 移除 `retryImport()` 的 client-only 实现，改为后端支持的方案 |
| `frontend/src/views/ChatView.vue` | 修复 `handleRetryImport()` 流程 |
| `frontend/src/views/ChatView.vue` | `onMounted` 中添加自动加载会话历史逻辑 |
| `backend/app/service_layer/api/import_routes.py` | 新增 `POST /import/retry/{paper_id}` 端点 |

### 不改动但涉及的文件

| 文件 | 原因 |
|------|------|
| `frontend/src/stores/library.ts` | 调用了 `fetchPapers`、`deletePaper`、`retryImport`，但接口不变 |
| `frontend/src/components/LibraryPanel.vue` | 重试按钮的 emit 逻辑不变 |

---

## 详细改动

### Fix 1: 修正 `fetchPapers()` 端点调用和字段映射

**根因**: 前端调用 `GET /api/v1/library/items`，后端返回 `LibraryItemOut`（字段 `item_id`、`page_count`），但前端代码映射 `library_item_id || paper_id`（都不存在），且期望 `total_pages`。

**方案**: 改为调用专门为前端兼容设计的 `GET /api/v1/papers`（`papers_routes.py:13`）。

`frontend/src/services/library-api.ts` 中 `fetchPapers()`:

```typescript
// 改前 (line 56-64)
export async function fetchPapers(): Promise<{ papers: PaperItem[] }> {
  const items = await request<PaperItem[]>('/api/v1/library/items')
  return { papers: (items as unknown as PaperItem[]).map(item => ({
    ...item,
    paper_id: item.library_item_id || item.paper_id,
    year: item.year ?? '',
    keywords: item.keywords ?? [],
  })) }
}

// 改后
export async function fetchPapers(): Promise<{ papers: PaperItem[] }> {
  const data = await request<{ papers: PaperItem[] }>('/api/v1/papers')
  return {
    papers: (data.papers || []).map(item => ({
      ...item,
      paper_id: item.paper_id || '',
      year: item.year ?? '',
      total_pages: (item as any).total_pages ?? 0,
      chunk_count: (item as any).chunk_count ?? 0,
      keywords: (item as any).keywords ?? [],
    })),
  }
}
```

**理由**: `PaperItemOut`（`papers_routes.py`）的字段与前端 `PaperItem` 接口几乎一致。`paper_id`、`total_pages`、`import_time`、`status` 都正确映射。

### Fix 2: 修复 `deletePaper()` 端点一致性

`frontend/src/services/library-api.ts` 中 `deletePaper()`:

```typescript
// 改前 (line 70-72)
export async function deletePaper(paperId: string): Promise<void> {
  await request(`/api/v1/library/items/${encodeURIComponent(paperId)}`, { method: 'DELETE' })
}

// 改后 — 改用 papers 路由（与 fetch 保持一致）
export async function deletePaper(paperId: string): Promise<void> {
  await request(`/api/v1/papers/${encodeURIComponent(paperId)}`, { method: 'DELETE' })
}
```

后端 `papers_routes.py:70` 已有 `DELETE /papers/{paper_id}`。

### Fix 3: 添加重试导入后端端点 + 修复前端调用

**根因**: `POST /api/v1/library/items/{id}/retry` 不存在。前端拿着 paper_id 但没有原始 File 对象，无法重新上传。

**方案**: 在 `import_routes.py` 添加 retry 端点（该文件已有所有 imports、`_run_import_with_progress` 和 `_compute_file_hash`），避免跨路由模块导入。

新增 `backend/app/service_layer/api/import_routes.py`（在 `start_import` 端点之后）:

```python
@router.post("/import/retry/{paper_id}", response_model=ImportStartResponse)
async def retry_import(paper_id: str, request: Request):
    """重新导入已有论文（复用原始文件路径）"""
    container = request.app.state.container
    item = container.library_repo.get(paper_id)
    if not item:
        raise HTTPException(status_code=404, detail="论文不存在")

    file_path = Path(item.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="原始文件不存在，请重新上传")

    task_id = uuid.uuid4().hex[:12]
    task = ImportTask(task_id=task_id, file_path=str(file_path))
    container.import_task_repo.create(task)
    asyncio.create_task(_run_import_with_progress(container, task_id, file_path))

    return ImportStartResponse(task_id=task_id, status="queued")
```

同步修复前端 `library-api.ts`:

```typescript
// 改前 (line 74-79) — 调用不存在的 /library/items/{id}/retry
// 改后 — 调用新的 /import/retry/{id}
export async function retryImport(paperId: string): Promise<ImportStartResult> {
  const result = await request<ImportStartResult>(
    `/api/v1/import/retry/${encodeURIComponent(paperId)}`,
    { method: 'POST' },
  )
  if (!result?.task_id) {
    throw new ApiClientError('重试导入失败：缺少 task_id')
  }
  return result
}
```

### Fix 4: 页面挂载时自动加载会话历史

**根因**: `ChatView.vue` 的 `onMounted` 没有调用 `listSessions()`。

在 `ChatView.vue` 的 `onMounted` 中（`probeBackend()` 成功后、配置检查之后）添加:

```typescript
// 在 onMounted 的 else 分支中，fetchBackendConfig() 之后添加:
sessionsLoading.value = true
try {
  sessions.value = await listSessions()
} catch {
  sessions.value = []
} finally {
  sessionsLoading.value = false
}
```

同时在会话列表加载后，如果有最近会话，自动选中第一个（可选，后续优化）。

### Fix 5: `probeBackend()` 改用正确的健康检查端点

```typescript
// 改前
const resp = await fetch('/api/v1/papers', { method: 'HEAD' })

// 改后
const resp = await fetch('/api/v1/health')
```

---

## 验证方式

1. **启动后端**: `cd backend && uv run python main.py`
2. **启动前端**: `cd frontend && pnpm dev`（端口 3893）
3. **验证 fix 1**: 访问 `http://localhost:3893`，导入一篇 PDF，确认文献列表正确显示 paper_id、标题、年份
4. **验证 fix 2**: 在文献列表中删除一篇论文，确认成功删除
5. **验证 fix 3**: 导入失败的论文出现重试按钮，点击重试，确认重新导入
6. **验证 fix 4**: 刷新页面，确认历史会话列表自动出现在侧边栏
7. **验证 fix 5**: 后端未启动时，页面自动进入 demo 模式
