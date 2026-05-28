# 前端优化：上传体验 & 文献库批量操作

> 生成时间: 2026-05-28
> 状态: 部分已实施（2026-05-29 评估）
>
> **已实施**: 文献库排序(2.3)、搜索功能(3.1)、上传进度 UI(1.4 部分)
> **待实施**: 后端 multipart 上传(1.1)、拖拽上传(1.2)、文件夹上传(1.3)、全选(2.1)、批量删除(2.2)

---

## 一、现状分析

### 1.1 文件上传

| 能力 | 状态 | 说明 |
|------|------|------|
| 点击上传 | ✅ 有 | `<input type="file" accept=".pdf">`，InputBar 和 LibraryPanel 两个入口 |
| 多文件选择 | ⚠️ 部分 | ChatView 的上传按钮有 `input.multiple = true`，但 InputBar 只取 `files[0]` |
| 拖拽上传 | ❌ 无 | 全局无 `@dragover` / `@drop` 逻辑 |
| 文件夹上传 | ❌ 无 | 未使用 `webkitdirectory` 属性 |
| 上传进度 | ⚠️ 数据有、UI 无 | store 有 `importPercent`/`importStep`，但未渲染到任何组件 |
| **前后端不匹配** | 🐛 Bug | 前端发 `FormData`（multipart），后端只接受 `{"file_path": "..."}` JSON |

### 1.2 文献库管理

| 能力 | 状态 | 说明 |
|------|------|------|
| 论文列表 | ✅ 有 | GET `/api/v1/library/items` |
| 搜索过滤 | ✅ 有 | 按标题/作者前端过滤 |
| 单选/多选 | ✅ 有 | 复选框 + `togglePaperSelection()` |
| 全选 | ❌ 无 | 无全选按钮 |
| 批量删除 | ❌ 无 | 只有单个删除 `DELETE /items/{id}` |
| 批量导入 API | ❌ 无 | 后端无 multipart 端点，无批量端点 |
| 排序 | ❌ 无 | 无排序选项 |
| 分页 | ❌ 无 | 一次加载全部 |

### 1.3 检索对话

| 能力 | 状态 | 说明 |
|------|------|------|
| 选论文后提问 | ✅ 有 | `paper_ids` 数组传给 `/api/v1/query`，后端 RAG 支持按 paper_ids 过滤 |
| 多论文检索 | ✅ 有 | 可勾选多篇论文一起检索（RRF 融合检索） |
| 全选 + 搜索 | ❌ 无 | LibraryPanel 无全选按钮 |

### 1.4 后端能力

| 能力 | 状态 | 说明 |
|------|------|------|
| 单文件导入（服务器路径） | ✅ 有 | POST `/api/v1/library/import`，接受 `{"file_path": "..."}` |
| Multipart 文件上传 | ❌ 无 | 后端无 multipart handler |
| 批量导入 | ⚠️ 仅 CLI | `scripts/batch_import.py`，且 import 路径过时 |
| 混合检索（Dense + Sparse + RRF） | ✅ 有 | 完整的 RAG pipeline |
| 按 paper_ids 过滤检索 | ✅ 有 | Dense/Sparse retriever 都支持 |
| 导入状态轮询 | ✅ 有 | GET `/api/v1/library/import/{task_id}` |
| 导入状态 SSE 流 | ✅ 有 | GET `/api/v1/library/import/stream/{task_id}`（前端未使用） |

---

## 二、实施计划

### Phase 1: 修复上传核心（高优先级）

> 目标：让文件上传真正可用

#### 1.1 后端：添加 multipart 文件上传端点

**文件**: `backend/app/service_layer/api/library_routes.py`

- 修改 `POST /api/v1/library/import`：
  - 接受 `UploadFile` (FastAPI 的 `File(...)`) 而非 JSON `file_path`
  - 保存到 `data/uploads/` 临时目录
  - 后续流程不变（hash 校验 → 创建 task → 异步处理）
- 新增 `POST /api/v1/library/import/batch`：
  - 接受多个 `UploadFile`
  - 为每个文件创建独立 import task
  - 返回 `[{task_id, filename}, ...]` 批量状态跟踪

**文件**: `backend/app/service_layer/schemas/library.py`

- 新增 `BatchImportResponse` schema
- 新增 `ImportStatusResponse` 统一格式

#### 1.2 前端：拖拽上传

**文件**: `frontend/src/views/ChatView.vue`

- 在最外层容器添加 `@dragover.prevent` / `@drop.prevent`
- drop 时过滤 `.pdf` 文件，调用 `libraryStore.importFiles()`
- 拖拽进入时显示全局拖拽提示浮层（"松开鼠标上传 PDF"）

**新建**: `frontend/src/components/DropOverlay.vue`

- 半透明遮罩 + 居中图标 + 提示文字
- enter/leave 动画 200ms

#### 1.3 前端：文件夹上传

**文件**: `frontend/src/components/LibraryPanel.vue`

- 上传按钮增加下拉菜单：单文件上传 / 文件夹上传
- 文件夹上传使用 `<input webkitdirectory>` 属性
- 过滤出 `.pdf` 文件后批量导入

#### 1.4 前端：上传进度 UI

**文件**: `frontend/src/components/LibraryPanel.vue` 或新建 `ImportProgressPanel.vue`

- 显示当前导入队列：文件名 + 步骤 + 进度条
- 使用 SSE 流（`/import/stream/{taskId}`）替代轮询
- 支持取消导入

---

### Phase 2: 文献库增强（中优先级）

> 目标：批量操作更高效

#### 2.1 全选按钮

**文件**: `frontend/src/components/LibraryPanel.vue`

- 表头添加全选复选框
- 搜索过滤后全选只选当前过滤结果
- 底部显示 "已选 N 篇 / 共 M 篇"

#### 2.2 批量删除

**文件**: `frontend/src/components/LibraryPanel.vue`

- 选中多篇后底部浮现操作栏：批量删除
- 确认弹窗显示数量

**文件**: `backend/app/service_layer/api/library_routes.py`

- 新增 `DELETE /api/v1/library/items/batch`
- 接受 `{item_ids: string[]}`，循环调用 `document_service.delete_document()`

#### 2.3 排序

**文件**: `frontend/src/components/LibraryPanel.vue`

- 下拉选择排序方式：按导入时间 / 按标题 / 按页数
- 前端排序即可，不需后端改动

---

### Phase 3: 搜索体验优化（低优先级）

#### 3.1 历史对话搜索

**文件**: `frontend/src/components/HistoryPanel.vue`

- 添加搜索框，按标题前端过滤

#### 3.2 文献库分页 / 虚拟滚动

- 论文数 > 100 时考虑虚拟滚动
- 当前阶段先跳过，等数据量上来再说

---

## 三、关键文件清单

| 文件 | 改动类型 |
|------|----------|
| `backend/app/service_layer/api/library_routes.py` | 修改：multipart 上传 + 批量端点 |
| `backend/app/service_layer/schemas/library.py` | 修改：新增 schema |
| `frontend/src/views/ChatView.vue` | 修改：拖拽事件绑定 |
| `frontend/src/components/LibraryPanel.vue` | 修改：全选、文件夹上传、进度 UI |
| `frontend/src/components/InputBar.vue` | 修改：多文件支持 |
| `frontend/src/components/DropOverlay.vue` | **新建**：拖拽浮层 |
| `frontend/src/stores/library.ts` | 修改：SSE 流式进度、批量操作 |

---

## 四、依赖关系

```
Phase 1.1（后端 multipart） → Phase 1.2（拖拽上传）→ Phase 1.4（进度 UI）
                          → Phase 1.3（文件夹上传）

Phase 2.1（全选）← 独立
Phase 2.2（批量删除）→ 需要后端 batch delete 端点
Phase 2.3（排序）← 独立，纯前端
```

Phase 1.1 是阻塞项，必须先完成后端 multipart 端点，前端的拖拽/批量上传才能工作。
