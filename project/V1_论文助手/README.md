# 论文助手 V1

基于 RAG 的学术写作助手，当前以 WPS 插件形态运行。

## 当前可用

- PDF 导入：支持单个导入、拖拽导入、批量顺序导入
- 导入去重：相同 PDF 会直接提示已导入
- 导入状态：前端轮询展示阶段进度，失败时直接显示真实阶段错误
- 断点恢复：后端按 `file_hash` 保存阶段产物，可从未完成阶段继续
- 检索增强：仅在选中文献时启用
- 来源展示：返回标题、页码、节名、摘录
- 历史对话：支持查看、续接、批量删除

## 快速开始

```bash
# 后端
cd backend
uv sync
cp .env.example .env
# 编辑 .env，填入你的 LLM API Key 和 Base URL
uv run python main.py

# 前端
cd ../frontend
pnpm install
pnpm dev --host 127.0.0.1 --port 3904

# 构建
pnpm build
```

后端默认运行在 `http://127.0.0.1:8000`，前端默认运行在 `http://127.0.0.1:3904/app.html`。

## 支持的 LLM 服务

后端使用 OpenAI 兼容协议，支持所有兼容 API：

| 服务商 | Base URL | Model 示例 |
|--------|----------|-----------|
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` |
| 智谱 (GLM) | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` |
| 硅基流动 | `https://api.siliconflow.cn/v1` | `deepseek-ai/DeepSeek-V3` |
| Kimi | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |

使用 Kimi Coding API 时会自动添加所需 headers，无需手动配置。

## 项目结构

```
V1_论文助手/
├── backend/            # FastAPI 后端
│   ├── app/
│   │   ├── api/        # API 路由
│   │   ├── clients/    # 外部服务客户端
│   │   ├── pipelines/  # 导入与检索管道
│   │   ├── stores/     # Chroma / BM25 / SQLite
│   │   └── core/       # 配置与错误处理
│   ├── data/           # app.db / chroma_db / bm25_index / backups / uploads / papers
│   └── .env.example
├── frontend/           # Vue 3 + TypeScript + Vite + WPS 插件壳
├── docs/               # 文档
└── test_meta_papers/   # 联调用测试 PDF
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端框架 | FastAPI (Python 3.13) |
| LLM/VLM | OpenAI 兼容协议（DeepSeek / 智谱 / 硅基流动 / Kimi 等） |
| Embedding | 硅基流动 Qwen3-Embedding-8B (1536 维) |
| 向量库 | ChromaDB |
| 关键词检索 | BM25 + jieba |
| 元数据与历史 | SQLite |
| PDF 解析 | MinerU API |
| 前端 | Vue 3 + TypeScript + Vite |
| 自动化验证 | Playwright |

## 当前主链

```text
PDF
  → MinerU 解析
  → VLM 图片理解
  → 清洗
  → 切块
  → Embedding
  → Chroma / BM25 / SQLite

用户提问
  → 是否选中文献
  → 仅在选中文献时启用检索增强
  → Dense + BM25 融合检索
  → LLM 流式生成
  → 返回可读来源
```

## 最近已验证

- 浏览器端上传 PDF 后可完成整条导入链
- 重复导入会返回明确提示，不再重复入库
- 导入失败会显示真实阶段错误，不再落成"导入状态丢失"
- 选中文献提问时可返回带来源的回答
- 历史对话可在侧栏立即刷新并重新打开
