# PRD: 侧边栏文献库学术搜索（v4.0 — 前后端联动，精简方案）

## 1. 目标

在 320px 侧边栏内，为已导入的本地论文提供学术级搜索体验。
**核心原则**：后端做最少的事（提取 PDF 元数据），搜索逻辑全在前端。

## 2. 现状问题

- 搜索仅 `title.includes(q)`，打错字就搜不到
- `authors` 字段后端有但永远为空，`year` 不存在
- 论文标题直接用文件名（`file_path.stem`），不读 PDF 元数据

## 3. 方案设计

### 3.1 UI：搜索 + 筛选内联，一个面板搞定

```
┌─ 320px 侧边栏 ────────────────────┐
│ [历史对话]  [文献库]            ✕  │
├───────────────────────────────────┤
│ 🔍 搜索标题、作者、关键词...      │
├───────────────────────────────────┤
│ [年份 ▼ 全部]  [作者 ▼ 全部]     │  ← 内联筛选
│ 排序: ●相关度 ○时间 ○年份 ○标题  │
├───────────────────────────────────┤
│ ☐ Attention Is All You Need       │
│   Vaswani · 2017 · 11页           │
│   [attention] [transformer]       │
│                   [🔗 找相似]     │
├───────────────────────────────────┤
│ ☐ BERT: Pre-training...           │
│   Devlin · 2019 · 16页            │
│   [BERT] [pre-training]           │
│                   [🔗 找相似]     │
├───────────────────────────────────┤
│ 共 5 篇，已选 2 篇               │
└───────────────────────────────────┘
```

不需要三个 tab 切换。搜索框 + 两个筛选下拉 + 排序 + 找相似按钮，全部内联。

### 3.2 搜索能力

| 能力 | 实现 | 后端需要？ |
|---|---|---|
| 模糊搜索（容错） | Fuse.js（前端） | ❌ |
| 按标题/作者/关键词搜索 | Fuse.js 多字段 | ❌ |
| 年份筛选 | 下拉选择（前端过滤） | ❌ |
| 作者筛选 | 下拉多选（前端聚合） | ❌ |
| 排序（相关度/时间/年份/标题） | 前端排序 | ❌ |
| 自动关键词提取 | 前端从 title 提取停用词后的高频词 | ❌ |
| 搜索高亮 | 前端 CSS | ❌ |
| 找相似论文 | 前端词汇交集（后续可升级向量搜索） | ❌ |
| 作者、年份数据 | PDF 元数据提取 | ✅ |

**后端唯一要做的事**：导入 PDF 时提取 `/Author` 和 `/CreationDate` 元数据。

### 3.3 找相似交互

点击论文卡片上的"找相似"按钮后，搜索框切换为相似模式：

```
┌───────────────────────────────────┐
│ 🔍 与 "Attention Is All You Need" │
│    相似的论文               [✕]   │
├───────────────────────────────────┤
│ 相似结果（按相关度排序）           │
│                                   │
│ ☐ BERT: Pre-training...   87%    │
│   Devlin · 2019                   │
│   共同词: [transformer]           │
│                                   │
│ ☐ GPT-4 Technical Report  52%    │
│   OpenAI · 2023                   │
│   共同词: [attention]             │
└───────────────────────────────────┘
```

点 ✕ 恢复正常搜索。

---

## 4. 后端改动（共 5 个文件）

### 4.1 新增 PDF 元数据提取函数

**新建** `backend/app/data_layer/preprocessing/transformation/pdf_metadata.py`：

```python
import pypdf
from pathlib import Path

def extract_pdf_metadata(file_path: str | Path) -> dict:
    """从 PDF 元信息中提取标题、作者、年份"""
    reader = pypdf.PdfReader(str(file_path))
    meta = reader.metadata or {}

    title = meta.get("/Title", "").strip()
    authors = meta.get("/Author", "").strip()

    # 从 CreationDate 提取年份: "D:20230615..." → 2023
    creation_date = meta.get("/CreationDate", "")
    year = ""
    if creation_date and len(creation_date) >= 5:
        try:
            year = str(int(creation_date[2:6]))
        except ValueError:
            pass

    # 如果元信息中没有标题，用文件名
    if not title:
        title = Path(file_path).stem

    return {"title": title, "authors": authors, "year": year}
```

### 4.2 LibraryItem 添加字段

**改** `backend/app/data_layer/contracts/library_item.py`：
```python
@dataclass
class LibraryItem:
    item_id: str
    title: str
    file_path: str
    file_hash: str = ""
    file_type: str = ""
    import_time: str = ""
    page_count: int = 0
    status: str = "ready"
    authors: str = ""    # 新增
    year: str = ""       # 新增
```

### 4.3 SQLite 表添加列

**改** `backend/app/data_layer/storage/sqlite_runtime/library_repo.py`：
```sql
CREATE TABLE IF NOT EXISTS library_items (
    ...
    authors TEXT DEFAULT '',   -- 新增
    year TEXT DEFAULT ''       -- 新增
)
```
同时在 `upsert()` 和 `_row_to_item()` 中同步这两个字段。

### 4.4 导入路由调用元数据提取

**改** `import_routes.py` 和 `library_routes.py` 中 `LibraryItem(...)` 构造处：

```python
from app.data_layer.preprocessing.transformation.pdf_metadata import extract_pdf_metadata

# 导入成功后
meta = extract_pdf_metadata(file_path)
container.library_repo.upsert(LibraryItem(
    item_id=result.paper_id,
    title=meta["title"] or file_path.stem,
    file_path=str(file_path),
    file_type=file_path.suffix.lower(),
    status="ready",
    authors=meta["authors"],
    year=meta["year"],
))
```

### 4.5 Schema 添加 year 字段

**改** `backend/app/service_layer/schemas/library.py`：
- `LibraryItemOut` 添加 `year: str = ""`
- `PaperItemOut` 添加 `year: str = ""`

---

## 5. 前端改动（共 8 个文件）

### 5.1 类型扩展

**改** `frontend/src/services/library-api.ts`：
- `PaperItem` 接口添加 `year?: string`, `keywords?: string[]`

### 5.2 Mock 数据补充

**改** `frontend/src/demo/index.ts`：
- 5 篇 demo 论文补充 `year` 和 `keywords` 字段

### 5.3 搜索核心逻辑

**新建** `frontend/src/composables/use-library-search.ts`：
- `parseQuery()` — 搜索解析（关键词提取，年份识别）
- `searchPapers()` — Fuse.js 多字段搜索
- `filterByYear()` / `filterByAuthor()` — 筛选
- `findSimilar()` — 词汇交集相似度
- `extractKeywords()` — 从 title 自动提取关键词
- `aggregateAuthors()` — 从论文列表聚合作者
- `aggregateYears()` — 从论文列表聚合年份范围

### 5.4 升级版论文卡片

**新建** `frontend/src/components/LibraryPaperCard.vue`：
- 显示年份、关键词标签（pill 样式）
- 搜索高亮
- 找相似按钮

### 5.5 重构文献库面板

**改** `frontend/src/components/LibraryPanel.vue`：
- 集成 Fuse.js 搜索
- 内联年份/作者筛选下拉
- 排序切换
- 相似搜索模式
- 用 LibraryPaperCard 替换现有的 label 列表项

### 5.6 安装 Fuse.js

```bash
cd frontend && pnpm add fuse.js
```

---

## 6. 实施步骤（按顺序执行）

| # | 任务 | 范围 | 涉及文件 |
|---|---|---|---|
| 1 | 安装 fuse.js | 前端 | `package.json` |
| 2 | 后端：PDF 元数据提取 | 后端 | 新建 `pdf_metadata.py` |
| 3 | 后端：LibraryItem + DB + Schema 扩展 | 后端 | 3 个文件 |
| 4 | 后端：导入路由调用元数据提取 | 后端 | 2 个 route 文件 |
| 5 | 前端：PaperItem 类型扩展 + mock 数据 | 前端 | 2 个文件 |
| 6 | 前端：搜索核心逻辑 composable | 前端 | 新建 `use-library-search.ts` |
| 7 | 前端：升级版论文卡片组件 | 前端 | 新建 `LibraryPaperCard.vue` |
| 8 | 前端：重构 LibraryPanel | 前端 | 重构 `LibraryPanel.vue` |
| 9 | 验证：dev server 跑通搜索全流程 | - | - |

---

## 7. 后续扩展（不在本次范围）

- 后端向量搜索 API → 升级"找相似"为真正的语义搜索
- 用户自定义标签（localStorage）
- 搜索历史记录
- 引用关系图谱
