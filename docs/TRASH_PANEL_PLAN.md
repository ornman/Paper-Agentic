# 回收站功能实现计划

## Context

当前删除论文时，`library_repo.delete()` 物理删除 SQLite 记录，用户刷新后论文消失但无法恢复。需要改为软删除（SQLite 加 `deleted_at` 列），并在 LibraryPanel 内部添加回收站视图，让用户可以查看和恢复已删除的论文。

## UI 交互

- LibraryPanel 底部已有的「🗑 回收站」按钮 → 点击后内容区切换为回收站视图
- 回收站顶部显示「← 返回文献库」导航头
- 每条已删除论文显示「恢复」和「永久删除」按钮
- 回收站为空时显示空状态提示

---

## Step 1：后端 — SQLite 软删除改造

### 1.1 `backend/app/data_layer/storage/sqlite_runtime/library_repo.py`

- `init()`：添加迁移 `ALTER TABLE library_items ADD COLUMN deleted_at TEXT DEFAULT NULL`
- `list_items()`：SQL 加 `WHERE deleted_at IS NULL`
- `list_items_filtered()`：同样加 `WHERE deleted_at IS NULL`
- `get()`：不加过滤（恢复时需要能 get 到已删除的）
- 新增 `soft_delete(item_id)`：`UPDATE library_items SET deleted_at = ? WHERE item_id = ?`
- 新增 `list_trashed()`：`SELECT ... WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC`
- 新增 `restore(item_id)`：`UPDATE library_items SET deleted_at = NULL WHERE item_id = ?`
- 新增 `hard_delete(item_id)`：`DELETE FROM library_items WHERE item_id = ?`（永久删除）
- `_row_to_item()`：增加 `deleted_at` 字段（index 11）

### 1.2 `backend/app/data_layer/storage/sqlite_runtime/_types.py`

- `LibraryItem` dataclass 加 `deleted_at: str | None = None`

### 1.3 `backend/app/data_layer/contracts/library_item.py`

- `LibraryItem` dataclass 同步加 `deleted_at: str | None = None`

### 1.4 `backend/app/service_layer/schemas/library.py`

- `LibraryItemOut` 加 `deleted_at: str | None = None`

---

## Step 2：后端 — API 端点

### `backend/app/service_layer/api/library_routes.py`

- `delete_item()`：改为调 `library_repo.soft_delete(item_id)` 替代 `library_repo.delete(item_id)`
- 新增 `GET /library/trash` → `list_trashed()` 返回已删除论文列表
- 新增 `POST /library/items/{item_id}/restore` → `restore()` + 取消索引软删除
- 新增 `DELETE /library/items/{item_id}/permanent` → `hard_delete()` + 索引硬删除

---

## Step 3：前端 — API 客户端

### `frontend/src/services/library-api.ts`

- 新增 `fetchTrashedPapers()`：`GET /api/v1/library/trash`
- 新增 `restorePaper(paperId)`：`POST /api/v1/library/items/{id}/restore`
- 新增 `permanentDeletePaper(paperId)`：`DELETE /api/v1/library/items/{id}/permanent`

---

## Step 4：前端 — Store

### `frontend/src/stores/library.ts`

- 新增 `trashedPapers: ref<PaperItem[]>([])`
- 新增 `loadTrashedPapers()`：调用 `fetchTrashedPapers()`
- 新增 `restorePaper(paperId)`：调 API → 从 trashedPapers 移除 → 刷新 papers
- 新增 `permanentDeletePaper(paperId)`：调 API → 从 trashedPapers 移除

---

## Step 5：前端 — TrashPanel.vue（新建）

路径：`frontend/src/components/TrashPanel.vue`

**Props**：
```ts
defineProps<{
  papers: PaperItem[]
  loading: boolean
}>()
```

**Events**：
```ts
defineEmits<{
  (e: 'restore', id: string): void
  (e: 'permanent-delete', id: string): void
  (e: 'back'): void
}>()
```

**结构**：header（← 返回文献库）+ body（已删除论文列表）+ empty state

---

## Step 6：前端 — LibraryPanel.vue 集成

- 新增内部状态 `viewMode: ref<'library' | 'trash'>('library')`
- 导入 `TrashPanel` 组件
- 回收站按钮 `@click` 改为 `viewMode = 'trash'`（不再 emit open-trash）
- body 区域根据 `viewMode` 条件渲染：
  - `'library'`：现有论文列表
  - `'trash'`：`<TrashPanel :papers="trashedPapers" @restore="..." @permanent-delete="..." @back="viewMode = 'library'" />`
- `viewMode` 切到 `'trash'` 时调 `libraryStore.loadTrashedPapers()`
- 恢复/永久删除后刷新列表

---

## 修改文件清单

| 文件 | 改动 |
|------|------|
| `backend/app/data_layer/storage/sqlite_runtime/library_repo.py` | 软删除 + 回收站 CRUD |
| `backend/app/data_layer/storage/sqlite_runtime/_types.py` | 加 deleted_at 字段 |
| `backend/app/data_layer/contracts/library_item.py` | 加 deleted_at 字段 |
| `backend/app/service_layer/schemas/library.py` | 加 deleted_at 字段 |
| `backend/app/service_layer/api/library_routes.py` | 改 delete + 3 个新端点 |
| `frontend/src/services/library-api.ts` | 3 个新 API 函数 |
| `frontend/src/stores/library.ts` | trashedPapers 状态 + 3 个方法 |
| `frontend/src/components/TrashPanel.vue` | **新建** |
| `frontend/src/components/LibraryPanel.vue` | viewMode 切换 + 集成 TrashPanel |
| `frontend/src/views/ChatView.vue` | 移除 open-trash 的 console.log（不再需要） |

## 验证

1. 启动后端 `uv run python main.py`
2. 启动前端 `pnpm dev`
3. 导入一篇论文 → 删除 → 刷新页面 → 确认论文不在列表
4. 点回收站按钮 → 确认看到已删除论文
5. 点「恢复」→ 确认论文回到文献库列表
6. 再删除 → 回收站 → 点「永久删除」→ 确认彻底消失
