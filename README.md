# 论文助手

基于 RAG 的学术写作助手，当前以 WPS 插件形态运行。

## 架构

```text
┌─────────────┐    HTTP/SSE    ┌─────────────────┐
│  Vue 3 前端  │ ◄────────────► │  FastAPI 后端    │
│  (WPS 插件)  │                │                 │
└─────────────┘                ├─────────────────┤
                               │ service_layer   │  ← API 路由 / DI / 配置
                               │ agent_layer     │  ← LLM 编排 / 检索 / 流式生成
                               │ data_layer      │  ← PDF 解析 / 向量库 / BM25
                               └─────────────────┘
```

**主链**:
```text
PDF 上传 → MinerU 解析 → VLM 图片描述 → 清洗 → 语义切块 → Embedding → Chroma + BM25

用户提问 → Query 改写 → Dense + BM25 融合检索 → LLM 流式生成 → 引用标注 → 返回前端
```

## 目录结构

```text
论文助手/
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── service_layer/    # API 路由 / DI 容器 / 配置 / 日志
│   │   ├── agent_layer/      # LLM 编排 / 检索 / 反思 / 流式生成
│   │   └── data_layer/       # PDF 解析 / 向量库 / BM25 / SQLite
│   ├── tests/                # 测试（unit / integration / e2e / soak）
│   ├── main.py               # 入口
│   └── pyproject.toml
├── frontend/                 # Vue 3 + TypeScript + WPS 插件壳
│   ├── src/
│   └── vite.config.ts
├── docs/                     # 文档与决策记录
│   └── backend/
│       └── server_layer_doc/ # API 接口文档
├── datasets/                 # 测试样本（不入版本控制）
├── log/                      # 运行日志（不入版本控制）
└── archives/                 # 历史版本归档
```

## 快速开始

### 环境要求

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- Node.js 18+ / pnpm

### 1. 启动后端

```bash
cd backend
uv sync
cp .env.example .env
# 编辑 .env 填入 API key
uv run python main.py
```

后端运行在 `http://127.0.0.1:8000`。Swagger 文档: `http://127.0.0.1:8000/docs`

### 2. 构建前端

```bash
cd frontend
pnpm install
pnpm build
cd dist
npx wpsjs debug
```

### 3. 环境变量

参见 `backend/.env.example`，核心配置：

| 变量 | 说明 |
|------|------|
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | LLM 服务配置 |
| `EMBEDDING_API_KEY` / `EMBEDDING_BASE_URL` / `EMBEDDING_MODEL` | Embedding 服务 |
| `EMBEDDING_DIMENSIONS` | Embedding 维度（默认 1536） |
| `MINERU_API_KEY` | MinerU PDF 解析 API |
| `VLM_API_KEY` / `VLM_BASE_URL` | VLM 图片理解 |
| `REFLECTION_API_KEY` / `REFLECTION_MODEL` | 反思模型（可选，不配则用主模型） |
| `REDIS_URL` | Redis（可选，不配则降级为内存缓存） |

## 测试

```bash
cd backend

# 单元测试（每次提交）
uv run pytest tests/agent_layer/unit tests/data_layer/unit tests/service_layer/unit -v

# 集成测试（需真实 API key）
uv run pytest tests/data_layer/integration -v -s

# 全部测试
uv run pytest tests/ -v
```

测试按 layer 组织：`backend/tests/{layer}/{unit,integration,e2e,soak}/`。

## 实验记录

实验数据与对比结果见 [LabRepo.md](LabRepo.md)。

## API 接口

详见 [API 接口文档](docs/backend/server_layer_doc/API接口文档.md)。

主要端点：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/health` | 健康检查 |
| GET | `/api/v1/papers` | 论文列表 |
| POST | `/api/v1/import/start` | 上传导入（multipart/form-data） |
| GET | `/api/v1/import/stream/{id}` | 导入进度（SSE） |
| POST | `/api/v1/query` | Agent 查询（SSE 流式） |
| POST | `/api/v1/conversations/chat` | 对话（SSE 流式） |
| GET | `/api/v1/library/items` | 文献库列表 |
| PUT | `/api/v1/assistant/selection` | 更新选中文本 |
| PUT | `/api/v1/assistant/written-context` | 更新已写内容 |
| POST | `/api/v1/models` | 模型发现 |

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vue 3 + TypeScript + Vite + WPS JS SDK |
| 后端 | FastAPI + Pydantic + asyncio |
| LLM | OpenAI 兼容 API（Kimi / LiteLLM） |
| Embedding | 硅基流动 Qwen3-Embedding-8B (1536 维) |
| 向量库 | ChromaDB (SQLite) |
| 关键词 | BM25 + jieba |
| PDF 解析 | MinerU API（远程） |
| 存储 | SQLite（对话/文献/任务） |
| 缓存 | Redis（可选，自动降级到内存） |
