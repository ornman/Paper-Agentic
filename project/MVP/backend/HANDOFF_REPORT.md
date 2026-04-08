# 接续报告 — MVP 论文写作助手

> **日期**: 2026-03-24
> **会话内容**: 修复断掉的工程 + 实现 Query 改写
> **项目路径**: `D:\同步\project\MVP`

---

## 本次完成的工作

### 1. 修复断掉的工程

上一个 AI 会话 API 报错后中断，留下以下问题：

| 问题 | 修复 |
|------|------|
| `cleaning_service.py` 用 `fitz.open()` 但 `import pymupdf` | 改为 `import fitz` |
| 4 个测试脚本全是乱码（AI 崩溃产物） | 删除，新写 5 个可运行的测试脚本 |
| `.env` 中 `EMBEDDING_DIMENSION=1536` | 改为 `4096`（匹配 API 实际返回） |

### 2. 验证全流程

| 测试 | 结果 |
|------|------|
| 单 PDF 清洗 | ✅ 18 段落，纯净度 72% |
| 批量清洗（9 PDF） | ✅ 9/9 成功，纯净度 91.3% |
| 完整三阶段（清洗→Embedding→索引） | ✅ 单 PDF 一次通过 |
| 批量三阶段（9 PDF） | ✅ 9/9 成功，345 向量+BM25 |
| 向量检索 | ✅ 语义相关结果正确 |
| BM25 关键词检索 | ✅ 分数排序正确 |

### 3. 实现 Query 改写（`query_rewrite_service.py`）

4 种场景全部实现并测试通过：

| 场景 | 输入 | 改写效果示例 |
|------|------|-------------|
| 1. 仅 prompt | "城乡公共文化服务有什么差距？" | → 3 个学术检索 query |
| 2. 仅已写内容 | 已写论文段落 → 推断续写意图 | → 3 个补充论据的检索 query |
| 3. 已写 + 圈选 | 圈选重点+上下文 | → 3 个围绕圈选内容的检索 query |
| 4. 已写 + 圈选 + prompt | 完整输入 | → 3 个精准检索 query |

### 4. 更新 retrieval_service.py

- 原来只支持单 query 检索
- 现在支持多 query（改写产出 1-3 个）并行检索 + RRF 融合
- Rerank 仍用原始 query（与用户意图对齐）

### 5. 更新 qa_service_rag.py

- 接入 query 改写
- 新增 `rewrite` SSE 事件（让前端知道查了什么）
- 返回值结构未变，向下兼容

---

## 当前项目状态

### 已完成

1. ✅ 会话管理（CRUD）
2. ✅ LLM 基础问答（流式 SSE）
3. ✅ PDF 清洗（PyMuPDF + 噪音过滤 v2）
4. ✅ PDF 导入三阶段（清洗 → Embedding → 索引）
5. ✅ 向量检索 + BM25 关键词检索
6. ✅ Query 改写（4 种场景）
7. ✅ RAG 问答服务代码（`qa_service_rag.py`）

### 待做

1. **⏳ 端到端 RAG 测试**：启动 FastAPI，通过 API 调用完整的 RAG 问答流程
   - `qa_service_rag.py` 代码已写好但未实际跑过
   - 需要确认 `query route` 调用的是 `qa_service_rag` 还是 `qa_service`
   - 检查 `app/api/v1/routes/query.py` 的路由指向

2. **⏳ 批量导入全部 PDF**（约 86 个）
   - 会消耗 Embedding API 额度
   - 用 `test_full_batch.py` 改一下路径就能跑

3. **⏳ 前端对接**

---

## 当前数据状态

- `data/cache/`: 9 个 JSON 缓存，全部 `indexed`
- `data/chroma/`: ChromaDB，345 条向量（4096 维）
- `data/bm25_index.json`: 927KB，345 条
- `data/app.db`: SQLite，会话+消息

---

## 文件变更清单

### 新增
- `app/services/query_rewrite_service.py` — Query 改写服务
- `test_clean.py` — 单 PDF 清洗测试
- `test_clean_batch.py` — 批量清洗测试
- `test_full_ingest.py` — 单 PDF 完整三阶段测试
- `test_full_batch.py` — 批量三阶段测试
- `test_retrieval.py` — 检索验证测试
- `test_query_rewrite.py` — Query 改写测试

### 修改
- `app/services/cleaning_service.py` — 修 import bug
- `app/services/retrieval_service.py` — 接入 query 改写，支持多路检索
- `app/services/qa_service_rag.py` — 接入改写后的检索服务
- `.env` — EMBEDDING_DIMENSION 1536 → 4096
- `CLAUDE.md` — 更新进度
- `INGEST_DESIGN.md` — 更新进度

### 删除
- `test_batch_ingestest_v2.py` — 乱码
- `test_cleaning_v2_simple.py` — 乱码
- `test_cleaning_only.py` — 乱码
- `test_cleaning_v2.py` — 乱码
- `test_ingest.py` — 旧版
- `test_rag.py` — 旧版
- `test_three_stage_ingest.py` — 旧版
- `test_ask.py` — 旧版

---

## 下次接续要点

1. 检查 `app/api/v1/routes/query.py`，确认路由指向 `qa_service_rag.ask_stream_with_rag` 而非 `qa_service.ask_stream`
2. 启动 FastAPI (`uv run python main.py`)，用 curl 测试 `/api/v1/query/ask` 端到端 RAG
3. 确认 Rerank API 正常工作（之前只测了 Embedding，没测 Rerank）
4. 额度充足时，批量导入全部 86 个 PDF
