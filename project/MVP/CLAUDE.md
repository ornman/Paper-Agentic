# Claude 配置 - MVP 项目

## 项目概况

**类型**: 学术写作助手（基于 RAG）  
**阶段**: MVP（最小可行产品）  
**架构**: 前后端分离 + 本地部署

## 技术栈

### 后端
- **框架**: FastAPI (Python 3.13)
- **LLM**: OpenAI 兼容协议（支持 DeepSeek/智谱/硅基流动）
- **向量库**: ChromaDB（本地持久化）
- **关键词检索**: rank_bm25 + jieba
- **Embedding**: 硅基流动 Qwen3-Embedding-8B (1536维)
- **Rerank**: 硅基流动 Qwen3-Reranker-8B
- **PDF 解析**: MinerU API（MVP 阶段）

### 前端
- **框架**: Vue 3 + TypeScript
- **构建**: Vite
- **部署**: WPS 插件

## 目录结构

```
MVP/
├── backend/           # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/   # 路由层
│   │   ├── clients/  # 外部服务客户端
│   │   ├── repositories/  # 数据仓储层
│   │   ├── services/ # 业务逻辑层
│   │   ├── models/   # 数据模型（Pydantic + SQLAlchemy）
│   │   └── core/     # 配置和工具
│   ├── main.py       # 启动入口
│   └── .env          # 环境变量（需手动配置）
├── frontend/         # Vue 3 前端（WPS 插件）
├── docs/
│   └── mvp/          # 设计文档
└── data/
    └── papers/       # 测试 PDF
```

## 开发规则

### 1. 优先级：先跑通基础问答

**当前阶段目标**：
1. ✅ 会话管理正常
2. ✅ LLM 问答正常（流式 SSE）
3. ✅ PDF 清洗（PyMuPDF + 噪音过滤管道 v2）
4. ✅ PDF 导入三阶段流程（清洗 → Embedding → 索引）
5. ✅ 向量检索（ChromaDB）+ 关键词检索（BM25 + jieba）
6. ✅ Query 改写逻辑（4 种场景，LLM 改写）
7. ⏳ 接入 RAG 检索到问答流程（混合检索 + RRF + Rerank → LLM）
8. ⏳ 批量导入全部 PDF（约 86 个）

**不追求完美**：MVP 阶段先验证核心流程，后续迭代优化。

### 2. 配置管理

**所有配置通过 `.env` 文件管理**：
- 后端配置：`backend/.env`
- 敏感信息（API Key）不提交 Git

**必须配置的环境变量**：
```env
# LLM（必填）
LLM_API_KEY=your_key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat

# 硅基流动（后续 RAG 需要）
EMBEDDING_API_KEY=your_key
RERANK_API_KEY=your_key
```

### 3. 代码风格

- **注释必须用中文**
- **函数必须有 docstring**
- **错误处理要完整**（不要静默失败）
- **不可变数据优先**（避免原地修改）

### 4. API 规范

**统一响应格式**：
```json
{
  "code": 0,
  "data": {...},
  "message": "success"
}
```

**流式输出**：使用 SSE (Server-Sent Events)
- 事件类型：`chunk`, `sources`, `done`, `error`

### 5. 测试策略

**MVP 阶段**：
- 手动测试为主（curl / Postman）
- 关键路径验证（创建会话 → 问答 → 查看历史）

**后续**：
- 单元测试（pytest）
- 集成测试（TestClient）

## 常用命令

### 后端

```bash
cd backend

# 安装依赖
uv sync

# 启动开发服务器
uv run python main.py

# 或直接用 uvicorn
uv run uvicorn app.main:app --reload

# 测试 API
curl http://localhost:8000/api/v1/health/
```

### 前端

```bash
cd frontend

# 安装依赖
pnpm install

# 开发模式
pnpm dev

# 构建
pnpm build
```

### Docker

```bash
# 一键启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止
docker-compose down
```

## 关键文档

| 文档 | 位置 | 说明 |
|------|------|------|
| 技术决策记录 | `docs/mvp/26-3-24-数据处理层技术决策记录.md` | 所有技术选型的 Q&A |
| 技术实现文档 | `docs/mvp/26-3-24-数据处理层技术实现文档.md` | 代码实现细节 |
| 导入设计（修正版） | `backend/INGEST_DESIGN.md` | 三阶段导入 + 断点续传 |
| API 文档 | http://localhost:8000/docs | FastAPI 自动生成 |

## 注意事项

1. **API Key 安全**：`.env` 文件已加入 `.gitignore`，切勿提交
2. **Python 版本**：要求 3.13+（使用了最新的类型提示语法）
3. **依赖管理**：使用 `uv` 而非 pip（更快）
4. **数据库**：SQLite 本地存储（`data/app.db`），首次启动自动创建

## 已知问题

- [x] ~~PDF 导入功能未实现（依赖 MinerU API）~~ → 已改用 PyMuPDF 直接解析，三阶段流程已跑通
- [x] ~~RAG 检索未接入~~ → 向量库和 BM25 已写入，检索验证通过
- [ ] RAG 检索未接入问答流程（检索结果还没传给 LLM）— 代码已写好，待端到端测试
- [x] ~~Query 改写逻辑未实现~~ → 4 种场景已实现并测试通过（`query_rewrite_service.py`）
- [ ] Embedding 维度实际为 4096（硅基流动 Qwen3-Embedding-8B 默认值），已更新 .env

## 已修复的 Bug（2026-03-24）

1. `cleaning_service.py` 的 `import pymupdf` → 改为 `import fitz`（原代码用 `fitz.open()` 但没 import fitz）
2. 删除了 4 个损坏的测试脚本（AI 生成中断导致的乱码文件）
3. `.env` 中 `EMBEDDING_DIMENSION=1536` → 改为 `4096`（匹配 API 实际返回）

## 下一步计划

1. 接入 RAG 检索（向量 + BM25 + Rerank）
2. 实现 PDF 导入流程
3. 前端对接后端 API
4. Docker 镜像优化
