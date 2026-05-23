# 论文助手

基于 RAG 的学术写作助手，当前以 WPS 插件形态运行。活动源码已提升到仓库根目录，`backend/` 和 `frontend/` 是当前唯一真相源，历史版本和旧数据统一归档到 `archives/`。

## 目录结构

```text
论文助手/
├── backend/                  # FastAPI 后端
├── frontend/                 # Vue 3 + TypeScript + WPS 插件壳
├── docs/                     # 项目文档与决策记录
├── datasets/
│   └── test_meta_papers/     # 样本/测试语料
├── archives/
│   ├── legacy/               # 历史版本与旧数据
│   └── packages/             # 历史压缩包
├── research/                 # 调研资料
└── AGENTS.md / CLAUDE.md     # 项目协作说明
```

## 快速开始

### 环境要求

- Python 3.13+
- uv
- Node.js 18+ / pnpm

### 1. 启动后端

```bash
cd backend
uv sync
cp .env.example .env
uv run python main.py
```

后端默认运行在 `http://127.0.0.1:8000`。

### 2. 构建前端并注册 WPS 插件

```bash
cd frontend
pnpm install
pnpm build
cd dist
npx wpsjs debug
```

`pnpm dev` 仍可用于浏览器侧调试，但正式使用需要通过 `wpsjs debug` 注册到 WPS。

## 当前主链

```text
PDF 上传
  → MinerU 解析
  → VLM 图片描述
  → 清洗
  → 切块
  → Embedding
  → Chroma / BM25 / SQLite

用户提问
  → 是否选中文献
  → Dense + BM25 融合检索
  → LLM 流式生成
  → 返回可读来源
```

## 主要目录约定

- `backend/data/`：运行态数据目录，承载 `app.db`、`chroma_db/`、`bm25_index/`、`papers/`、`parsed/`、`uploads/`、`backups/`
- `datasets/test_meta_papers/`：联调用测试 PDF
- `archives/legacy/`：MVP、旧布局数据、提取产物
- `archives/packages/`：历史压缩包

## 文档

- [开发文档总览](docs/开发文档/README.md)
- [V1 架构设计](docs/开发文档/02-设计/架构/V1-架构设计.md)
- [API 接口文档](docs/开发文档/02-设计/API/API接口文档.md)
- [开发指南](docs/开发文档/03-开发/开发指南.md)
