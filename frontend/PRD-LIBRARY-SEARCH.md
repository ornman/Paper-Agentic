# PRD: 侧边栏文献库学术搜索（v3.0 — 基于本地项目实际代码）

## 1. 现状（实际代码分析）

### 当前搜索能力（极弱）

`LibraryPanel.vue:165-173` — 搜索逻辑：
```typescript
// 仅 title 和 authors 的 includes 模糊匹配
const filteredPapers = computed(() => {
  if (!searchText.value.trim()) return props.papers
  const q = searchText.value.toLowerCase()
  return props.papers.filter(p =>
    paper.title.toLowerCase().includes(q) ||
    paper.authors.toLowerCase().includes(q),
  )
})
```

### 当前 UI 布局（320px 侧边栏）

`SidebarDrawer.vue:107` — 侧边栏固定宽度 320px，非常窄，搜索 UI 必须紧凑：
```
┌─ 320px ─────────────────────────┐
│ [历史对话]  [文献库]          ✕  │  ← tab 切换
├─────────────────────────────────┤
│ 🔍 搜索论文...            [排序]│  ← 当前搜索框
│ [上传论文]                       │
│ ☐ Attention Is All You Need     │
│   Vaswani et al. · 11页 · 47块  │
│   ...                           │
└─────────────────────────────────┘
```

### 当前论文数据结构

`library-api.ts:5-18` — `PaperItem` 接口：
```typescript
interface PaperItem {
  paper_id: string
  title: string
  authors: string        // 后端返回空字符串，demo 模式有值
  file_path: string
  file_hash: string
  chunk_count: number
  total_pages: number
  import_time: string
  status: string
  library_item_id: string
  kind: string
  file_size: number | null
}
```

### 后端数据缺失

`library_repo.py:23-34` — DB 表只有 7 个字段：
```sql
CREATE TABLE library_items (
  item_id, title, file_path, file_hash,
  file_type, import_time, page_count, status
)
```
**没有**: year, keywords, abstract, doi, journal。`authors` 在 schema 存在但永远为空。

### Demo 模式（可利用）

`demo/index.ts:13-84` — 5 篇 mock 论文，有完整 authors、不同年份（隐含在 title/content 中）。
Demo 模式可用于验证搜索 UI，但需要给 mock 数据补上 `year` 和 `keywords` 字段。

---

## 2. 改造方案

### 设计约束（来自实际代码）

1. **320px 宽度**：筛选面板不能太宽，用折叠/展开方式
2. **不破坏现有功能**：选择论文、上传、删除、排序这些已有功能保留
3. **先跑通前端**：后端没有搜索 API，前端内存过滤 + Mock 数据先上
4. **复用已有基础设施**：`library.ts` store 的 `filteredPapers` computed、`library-api.ts` 的类型定义

### 三种搜索模式

在现有搜索框的位置，升级为三种搜索模式，通过 tab 切换：

```
┌─ 320px ──────────────────────────┐
│ [🔍 搜索]  [📊 筛选]  [🔗 相似] │  ← 模式切换
├──────────────────────────────────┤
│ （当前模式的 UI 内容区）          │
└──────────────────────────────────┘
```

---

### 模式 A：智能搜索（默认）

替换当前的搜索框。一个输入框，自动识别搜索意图：

```
┌──────────────────────────────────┐
│ 🔍 输入关键词、作者、年份...      │
├──────────────────────────────────┤
│  👤 Vaswani  📅 2017  🏷️ attention │  ← 自动解析标签
├──────────────────────────────────┤
│ ☐ Attention Is All You Need      │
│   Vaswani · 2017 · 11页          │
│   [transformer][attention]        │
│ ☐ BERT: Pre-training...          │
│   Devlin · 2019 · 16页           │
│   [NLP][pre-training]            │
└──────────────────────────────────┘
```

**识别规则（轻量级前端解析）：**

| 输入 | 识别为 | 示例 |
|---|---|---|
| 4 位数字 | 年份 | `2023` |
| `数字-数字` | 年份范围 | `2020-2024` |
| 2-4 个中文字 | 候选作者 | `张三` |
| 英文/技术词 | 关键词（匹配 title + keywords） | `transformer` |
| `author:xxx` | 强制作者 | `author:vaswani` |
| `title:xxx` | 强制标题匹配 | `title:attention` |
| 混合输入 | AND 组合 | `vaswani 2017 transformer` |
| 长中文句子 | 全文模糊 | `预训练语言模型` |

---

### 模式 B：可视化筛选

可展开的结构化筛选器，替代复杂的搜索语法：

```
┌──────────────────────────────────┐
│ 📅 年份                          │
│ [2018] ─────●──── [2024]         │
│                                  │
│ 👤 作者                          │
│ [▼ 选择已有作者...]               │
│ ✕ Vaswani  ✕ Devlin  [+添加]     │
│                                  │
│ 🏷️ 关键词                        │
│ [NLP] [Transformer] [+ 添加]     │
│                                  │
│ 📊 排序  ● 相关性 ○ 年份 ○ 时间  │
│                                  │
│        [重置筛选条件]              │
└──────────────────────────────────┘
```

**数据来源（前端聚合）：**
- 作者列表：从 `papers.map(p => p.authors).flatMap(...)` 提取去重
- 年份范围：从 `papers.map(p => p.year)` 取 min-max
- 关键词列表：从 `papers.map(p => p.keywords).flatMap(...)` 提取去重

---

### 模式 C：相似论文搜索

选中一篇已有论文或输入描述，找内容最接近的论文：

```
┌──────────────────────────────────┐
│ 基准论文：                        │
│ [▼ 选择一篇论文...]               │
│                                  │
│ 或描述你想找的内容：               │
│ [关于强化学习训练大语言模型的方法]  │
│                                  │
│ [🔍 查找相似论文]                 │
├──────────────────────────────────┤
│ 相似结果（按相关度排序）           │
│                                  │
│ ┌────────────────────────────┐  │
│ │ GPT-4 Technical Report     │  │
│ │ 相似度: 87%                 │  │
│ │ OpenAI · 2023 · 100页      │  │
│ └────────────────────────────┘  │
└──────────────────────────────────┘
```

**Phase 1 实现（前端关键词匹配）：**
- 选定论文后，提取其 title + keywords 的词汇
- 与其他论文的 title + keywords 计算词汇交集/TF-IDF 相似度
- 按相似度排序返回 top 10

**Phase 2 实现（后端向量搜索）：**
- 后端利用已有 ChromaDB 向量索引，添加 paper-level 的语义搜索 API

---

### 搜索结果卡片（统一）

三种模式共享结果列表，升级现有卡片：

```
┌──────────────────────────────────┐
│ ☐ Attention Is All You Need      │  ← 标题（高亮匹配词）
│   Vaswani et al. · 2017          │  ← 作者 + 年份（新增）
│   [transformer] [attention]       │  ← 关键词标签（新增）
│   11页 · 47块 · 3天前导入         │  ← 原有 meta
│                        [🔗找相似] │  ← 新增按钮
└──────────────────────────────────┘
```

---

## 3. 改造范围（具体文件）

### 修改的文件

| 文件 | 改动内容 |
|---|---|
| `library-api.ts` | `PaperItem` 接口添加 `year?`, `keywords?`, `abstract?` 可选字段 |
| `library.ts` (store) | 新增搜索状态（模式、筛选条件）、聚合作者/关键词列表、统一搜索入口 |
| `LibraryPanel.vue` | 替换现有搜索为三模式 tab 布局，接入新搜索组件 |
| `demo/index.ts` | mock 论文数据补充 `year` 和 `keywords` 字段 |

### 新建的文件

| 文件 | 内容 |
|---|---|
| `composables/use-library-search.ts` | 搜索核心逻辑：智能解析、筛选过滤、相似度计算 |
| `components/LibrarySearchBar.vue` | 模式 A：智能搜索框 + 意图解析标签 |
| `components/LibraryFilterPanel.vue` | 模式 B：年份滑块 + 作者多选 + 关键词标签 |
| `components/LibrarySimilarSearch.vue` | 模式 C：相似论文搜索面板 |
| `components/LibraryPaperCard.vue` | 升级版论文卡片（年份、关键词、高亮、找相似） |

### 不动的文件

- `SidebarDrawer.vue` — 布局不变，LibraryPanel 通过 slot 嵌入
- `ChatView.vue` — 侧栏集成方式不变
- `ui.ts` — 不需要新状态
- 后端代码 — 本次不动，先纯前端

---

## 4. 数据流设计

```
用户输入/筛选
    │
    ▼
use-library-search.ts（composable）
    ├── parseSmartQuery()      → 智能搜索解析
    ├── applyFilters()         → 筛选面板逻辑
    ├── findSimilar()          → 相似度计算
    └── search()               → 统一入口，返回过滤后结果
    │
    ▼
LibraryPanel.vue
    └── LibraryPaperCard.vue   → 渲染结果列表
```

**核心接口：**

```typescript
// use-library-search.ts
interface SearchState {
  mode: 'smart' | 'filter' | 'similar'
  rawQuery: string
  parsed: ParsedQuery       // 智能搜索解析结果
  filters: FilterState      // 筛选面板状态
  similarTo: string | null  // 相似搜索基准 paper_id
  sort: 'relevance' | 'time' | 'year' | 'title'
  sortDir: 'asc' | 'desc'
}

interface ParsedQuery {
  authors: string[]
  keywords: string[]
  yearExact?: number
  yearFrom?: number
  yearTo?: number
  fullText: string
}

interface FilterState {
  yearFrom?: number
  yearTo?: number
  authors: string[]
  keywords: string[]
}

// 统一搜索函数，后续切后端只改这里
function searchPapers(
  papers: PaperItem[],
  state: SearchState
): PaperItem[]
```

---

## 5. Mock 数据补充

`demo/index.ts` 中的 5 篇论文需要补充 year 和 keywords：

```typescript
// paper-1: Attention Is All You Need
year: 2017, keywords: ['transformer', 'attention', 'NLP', 'seq2seq']

// paper-2: BERT
year: 2019, keywords: ['NLP', 'pre-training', 'BERT', 'language-model']

// paper-3: ResNet
year: 2016, keywords: ['CV', 'residual-learning', 'deep-network', 'image-recognition']

// paper-4: GAN
year: 2014, keywords: ['GAN', 'generative-model', 'adversarial-training']

// paper-5: GPT-4
year: 2023, keywords: ['LLM', 'GPT', 'multimodal', 'RLHF']
```

同时 `PaperItem` 接口添加可选字段：
```typescript
year?: number
keywords?: string[]
abstract?: string
```

---

## 6. 实施步骤（按顺序）

| # | 任务 | 涉及文件 |
|---|---|---|
| 1 | `PaperItem` 接口扩展 + mock 数据补充 | `library-api.ts`, `demo/index.ts` |
| 2 | `use-library-search.ts` 搜索核心逻辑 | 新建 composable |
| 3 | `LibraryPaperCard.vue` 升级版论文卡片 | 新建组件 |
| 4 | `LibrarySearchBar.vue` 智能搜索框 | 新建组件 |
| 5 | `LibraryFilterPanel.vue` 可视化筛选 | 新建组件 |
| 6 | `LibrarySimilarSearch.vue` 相似搜索 | 新建组件 |
| 7 | `LibraryPanel.vue` 集成三模式搜索 | 重构现有组件 |
| 8 | `library.ts` store 扩展搜索状态 | 修改 store |
| 9 | dev server 验证三种搜索模式完整流程 | - |

---

## 7. 后端对接预留（后续，不在本次范围）

**需要后端同事做的事：**
1. DB 表添加 `authors`, `year`, `keywords`, `abstract` 字段
2. 导入时从 PDF 提取元数据（或调用 LLM 提取 keywords）
3. `GET /api/v1/papers/search` 搜索 API（参数与前端 `SearchParams` 对齐）
4. `POST /api/v1/papers/similar` 语义相似搜索（利用已有 ChromaDB 向量索引）

前端届时只需在 `use-library-search.ts` 中将 `searchPapers()` 的实现从前端内存过滤切换为 API 调用。
