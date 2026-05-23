# 论文写作助手 MVP

基于 RAG（检索增强生成）的学术写作辅助系统。

## 项目结构

```
MVP/
├── backend/           # FastAPI 后端服务
│   ├── app/           # 应用代码
│   ├── main.py        # 启动入口
│   └── pyproject.toml # Python 依赖
├── frontend/          # WPS 插件前端
│   ├── src/           # Vue 3 源码
│   └── dist/          # 构建产物
├── docs/              # 技术文档
│   └── mvp/           # MVP 设计文档
├── data/              # 测试数据
│   └── papers/        # PDF 文献库
└── docker-compose.yml # 一键部署配置
```

## 快速开始

### 环境要求

- Python 3.13+
- Node.js 18+ / pnpm
- Docker & Docker Compose（可选）

### 本地开发

#### 1. 后端启动

```bash
cd backend

# 安装依赖
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key

# 启动服务
uv run python main.py
```

访问 http://localhost:8000/docs 查看 API 文档。

#### 2. 前端启动（WPS 插件）

```bash
cd frontend

# 安装依赖
pnpm install

# 开发模式
pnpm dev

# 构建生产版本
pnpm build
```

### Docker 部署

```bash
# 一键启动
docker-compose up -d

# 查看日志
docker-compose logs -f backend
```

## 核心功能

### MVP 阶段（当前）

- ✅ 会话管理（创建/列表/删除）
- ✅ 基础问答（LLM 直接调用）
- ✅ 流式输出（SSE）
- ✅ 上下文管理（LangChain Memory）
- ⏳ RAG 检索增强
- ⏳ PDF 导入与解析

### 后续规划

- 语义切分与知识图谱
- 多格式支持（Word/PPT）
- 检索策略可配置

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/health` | GET | 健康检查 |
| `/api/v1/session` | POST | 创建会话 |
| `/api/v1/session` | GET | 获取会话列表 |
| `/api/v1/session/{id}` | GET | 获取会话详情 |
| `/api/v1/session/{id}/history` | GET | 获取历史消息 |
| `/api/v1/query/ask` | POST | 流式问答（SSE） |
| `/api/v1/config` | GET | 获取配置 |
| `/api/v1/config/test` | POST | 测试连接 |

## 技术栈

### 后端

- **框架**: FastAPI
- **LLM**: OpenAI 兼容协议（DeepSeek/智谱/硅基流动）
- **向量库**: ChromaDB
- **关键词检索**: rank_bm25 + jieba
- **Embedding**: Qwen3-Embedding-8B
- **Rerank**: Qwen3-Reranker-8B
- **PDF 解析**: MinerU API

### 前端

- **框架**: Vue 3 + TypeScript
- **构建**: Vite
- **UI**: 原生 WPS 插件 API

## 文档

详细设计文档位于 `docs/mvp/`：

- [数据处理层技术决策记录](docs/mvp/26-3-24-数据处理层技术决策记录.md)
- [数据处理层技术实现文档](docs/mvp/26-3-24-数据处理层技术实现文档.md)

## License

MIT
