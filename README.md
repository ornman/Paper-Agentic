# 论文写作助手 MVP

> 基于 RAG（检索增强生成）的学术写作辅助系统，以 WPS 插件形式嵌入写作场景。

## 快速开始

### 环境要求

- Python 3.13+
- Node.js 18+ / pnpm
- uv（Python 包管理器）

### 本地开发

#### 1. 后端启动

```bash
cd project/MVP/backend

# 安装依赖
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入必要的 API Key

# 启动服务
uv run python main.py
```

访问 http://localhost:8000/docs 查看 API 文档。

#### 2. 前端启动（WPS 插件）

```bash
cd project/MVP/frontend

# 安装依赖
pnpm install

# 开发模式
pnpm dev

# 构建生产版本
pnpm build
```

### Docker 部署

```bash
# 一键启动（待实现）
docker-compose up -d
```

## 核心功能

### MVP 阶段（当前）

- ✅ 会话管理（创建/列表/删除）
- ✅ 基础问答（LLM 直接调用）
- ✅ 流式输出（SSE）
- ✅ 上下文管理
- ✅ PDF 导入（MinerU + 清洗 + VLM + 切分 + 索引）
- ✅ RAG 检索增强
- ⏳ 前后端完整对接

### 技术亮点

- **混合切分策略**：智能打包 + 平均切分 + 首尾重叠
- **抽象接口设计**：VLM/LLM 客户端可替换
- **分布式向量库**：Qdrant 每篇论文独立 collection
- **低幻觉图片描述**：优化 prompt，针对论文图表

## 架构设计

### 数据流

```
PDF 导入：用户上传 → MinerU API → 清洗 → VLM 描述 → 混合切分 → Embedding → Qdrant
RAG 问答：用户提问 → Query 改写 → Qdrant 检索 → Rerank → LLM → 流式返回
```

### 技术栈

| 组件 | 技术 |
|------|------|
| **后端框架** | FastAPI |
| **LLM/VLM** | Kimi Coding API (kimi-for-coding) |
| **Embedding** | 硅基流动 Qwen3-Embedding-8B (1536维) |
| **Rerank** | 硅基流动 Qwen3-Reranker-8B |
| **向量库** | Qdrant（分布式隔离） |
| **PDF 解析** | MinerU API |
| **前端框架** | Vue 3 + TypeScript |
| **状态管理** | Pinia |
| **构建工具** | Vite |

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/health` | GET | 健康检查 |
| `/api/v1/session` | POST | 创建会话 |
| `/api/v1/session` | GET | 会话列表 |
| `/api/v1/query/ask` | POST | 流式问答（SSE） |
| `/api/v1/library/import` | POST | 导入 PDF |
| `/api/v1/library/papers` | GET | 论文列表 |
| `/api/v1/library/papers/{id}` | GET | 论文详情 |
| `/api/v1/library/papers/{id}` | DELETE | 删除论文 |

## 配置说明

### 必需环境变量

```env
# Kimi Coding API（VLM + LLM）
KIMI_API_KEY=your_key

# 硅基流动（Embedding + Rerank）
SILICONFLOW_API_KEY=your_key
```

### 可选配置

```env
# MinerU API（PDF 解析）
MINERU_API_KEY=your_key

# 切分策略参数
CHUNK_MAX_CONTEXT=32000
CHUNK_TARGET_SIZE=24000
CHUNK_OVERLAP_BUFFER=8000

# 服务端口
APP_PORT=8000
```

## 文档

- [架构分析报告](docs/架构分析报告.md)
- [流程架构图](docs/流程架构图.md)
- [北极星文档](docs/北极星.md)

## 开发规范

### 代码风格

- 注释必须用中文
- 函数必须有 docstring
- 错误处理要完整
- 不可变数据优先

### 抽象接口

```python
# VLM/LLM 客户端抽象接口
from app.clients.vlm_client import VLMClient, LLMClient

# 使用抽象接口，可替换实现
async def process_image(vlm_client: VLMClient):
    return await vlm_client.describe_image(path)
```

## License

MIT
