# 论文助手 V1

基于 RAG 的学术写作助手，WPS 插件形态。

## 快速开始

```bash
# 后端
cd backend
uv sync
cp .env.example .env   # 配置 API keys
uv run python main.py

# 测试
uv run pytest tests/ -v
```

## 项目结构

```
V1_论文助手/
├── backend/            # FastAPI 后端
│   ├── app/            # 源码
│   │   ├── api/        # API 路由
│   │   ├── clients/    # 外部服务客户端
│   │   ├── pipelines/  # 数据管道（导入/检索）
│   │   ├── stores/     # 存储层
│   │   └── core/       # 配置与错误处理
│   ├── tests/          # 测试
│   └── scripts/        # 工具脚本
├── frontend/           # Vue 3 前端（WPS 插件）
├── docs/               # 文档
│   ├── api/            # API 文档
│   ├── architecture/   # 架构设计
│   └── development/    # 开发指南
└── test_meta_papers/   # 测试用 PDF
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端框架 | FastAPI (Python 3.13) |
| LLM/VLM | Kimi Coding API |
| Embedding | 硅基流动 Qwen3-Embedding-8B (1536维) |
| 向量库 | Zvec |
| 关键词检索 | BM25 + jieba |
| PDF 解析 | MinerU API |
| 前端 | Vue 3 + TypeScript + Vite |

## 数据流

```
PDF → MinerU 解析 → VLM 图片描述 → 清洗 → 切块 → Embedding → Zvec/BM25
                                                               ↓
用户提问 → Embedding → Zvec 检索 → BM25 检索 → 融合 → LLM 生成 → SSE 流式返回
```
