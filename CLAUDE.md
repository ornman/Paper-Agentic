# Claude 配置 - 论文助手项目

## 项目概况

**类型**: 学术写作助手（基于 RAG）
**阶段**: MVP（最小可行产品）
**架构**: 前后端分离 + 本地部署

## 快捷命令

### 四维度决策快照

```bash
# 基于代码事实解剖项目，产出验尸报告
/update-snapshot
```

### 日志系统（调试必用）

日志目录 `log/`（项目根目录），JSON Lines 格式：
| 文件 | 内容 |
|------|------|
| `app.log` | 全部后端运行日志（结构化 JSON Lines） |

**用户说"不成功"/"报错"/"失败了"时 → 先读日志再排查。**

---

## 核心理念：代码不会说谎，文档会

基于第一性原理：**代码是唯一的真实态，文档只是理想态的投影。** 文档的价值不在于描绘"设计应该是什么"，而在于记录"为什么这样选、踩过什么坑、什么还没做"。

**原则**：
- **代码是真相源**，文档是决策记录——两者矛盾时信代码
- **扩展点先写代码**，用 `🔮 未来扩展` 标注，再同步文档
- **文档只记录"为什么"**：为什么选 A 不选 B，A 的代价是什么，什么条件下会失效
- **快照 ≠ 售前 PPT**，是验尸报告 + 体检报告：记录约束、腐化点、已知风险

**四维度认知模型**（快照必须覆盖）：

| 维度 | 关注点 | 缺失的后果 |
|------|--------|-----------|
| **静态结构** | 模块依赖方向（非分层方块）、API 调用矩阵 | 以为分层清晰，实际有循环依赖/跨层穿透 |
| **动态行为** | 关键路径时序、降级逻辑、状态机 | 以为流程是直线，实际满是分支和重试 |
| **物理部署** | 外部依赖拓扑、端口映射、配置差异 | 本地跑通 ≠ 部署可用（CORS、权限、网络） |
| **演进与债务** | Git 变更热力图、TODO/FIXME 密度、已知风险 | 高频变动文件 = Bug 巢穴，僵尸代码 = 隐藏地雷 |

---

## 技术栈

### 后端
- **框架**: FastAPI (Python 3.13)
- **LLM/VLM**: Kimi Coding API (kimi-for-coding)
- **向量库**: Chromadb（纯 Python，SQLite 持久化）
- **关键词检索**: BM25 + jieba
- **Embedding**: 硅基流动 Qwen3-Embedding-4B (1536维)
- **Rerank**: 硅基流动 Qwen3-Reranker-8B（已集成，未启用）
- **PDF 解析**: MinerU API（远程解析）

### 前端
- **框架**: Vue 3 + TypeScript
- **构建**: Vite
- **部署**: WPS 插件

---

## 目录结构

```
论文助手/
├── backend/                  # 当前活动后端
│   ├── app/
│   ├── scripts/
│   ├── data/                 # 运行态数据
│   ├── main.py
│   └── pyproject.toml
├── frontend/                 # 当前活动前端（WPS 插件）
│   ├── src/
│   ├── wps-plugin/
│   └── vite.config.ts
├── docs/                     # 全局文档
│   ├── Decision-Snapshot/    # 四维度决策快照
│   │   ├── 1-静态结构/       # 模块边界、存储模型、接口定义、代码组织
│   │   ├── 2-动态行为/       # 业务时序、错误传播、状态机、并发调度
│   │   ├── 3-物理部署/       # 依赖拓扑、资源配置、环境差异
│   │   └── 4-演进与债务/     # 变更热点、架构适应度、失效模式、演进路线
│   └── 账单/                 # 经费记录
├── datasets/                 # 测试样本（自备 PDF，不入版本控制）
│   ├── 中文文献-测试-PDF/    # 中文论文 PDF（集成测试用）
│   ├── 外文文献-测试-PDF/    # 外文论文 PDF（集成测试用）
│   └── README.md
├── archives/                 # 历史版本与旧数据归档
│   ├── legacy/
│   └── packages/
├── research/                 # 调研资料
└── .tools/rag/               # 微 RAG 知识库
```

---

## 开发规则

### 0. Git 提交规则（硬规则）

**禁止主动 commit**：除非用户明确说"提交"/"commit"，否则不创建任何 commit。

**提交格式**：用户发起 commit 时会附带自己的描述。commit message 结构如下：

```
<类型>: <简短标题>

<基于代码 diff 的事实摘要：改了哪些文件、改了什么，只记录事实，不记录推断>

---

"用户原话，一字不改"
```

**事实摘要规范**：
- 只记录从 `git diff` 中能直接读到的事实：哪些文件变了、函数签名改了、参数增删了、逻辑分支变了
- 禁止主观判断：不说"优化了"、"改进了"、"更好地"，只说"将 X 改为 Y"、"删除了 Z"
- 不推断动机：不说"为了支持 XXX"、"为了更好地 YYY"
- 用户的 message 是唯一允许的主观内容，必须原话保留，用 `---` 分隔后加双引号包裹
- 如果用户追问改动细节或技术问题，如实基于代码回答即可

### 1. 数据流架构（重要）

**PDF 导入流程**：
```
用户上传 PDF → MinerU API 解析 → 清洗 → VLM 图片描述 → 混合切分 → Embedding → Qdrant 存储
```

**RAG 问答流程**：
```
用户提问 → Query 改写 → Qdrant 检索 → Rerank → LLM 生成 → 流式返回
```

### 2. 切分策略（核心）

| 条件 | 处理方式 |
|------|----------|
| 两个语义块 ≤ 32k | 打包一起，一次 API 请求 |
| 超过 32k，单个都不超过 | 分开，不用重叠 |
| 超过 32k，单个也超过 | 平均切分到 24k，首尾重叠接近 32k |

### 3. 抽象接口（可替换）

```python
# VLMClient - 图片描述
class VLMClient(ABC):
    async def describe_image(image_path, prompt) -> str: ...

# LLMClient - 聊天对话
class LLMClient(ABC):
    async def chat(messages) -> str: ...
    async def chat_stream(messages): ...

# EmbeddingClient - 向量化
class EmbeddingClient(ABC):
    async def embed(texts) -> list[list[float]]: ...
    async def embed_single(text) -> list[float]: ...

# RerankClient - 重排序
class RerankClient(ABC):
    async def rerank(query, documents, top_k) -> list[tuple[int, float]]: ...

# 当前实现：KimiVLMClient, KimiLLMClient, SiliconFlowEmbeddingClient, SiliconFlowRerankClient
# 未来可替换为：OpenAI、Azure、其他
```

### 4. 前后端边界

- **前端**：只负责交互、状态管理、数据展示
- **后端**：所有业务逻辑、数据处理、外部服务调用

### 5. 分布式架构决策

**为什么选分布式（每篇论文一个 Collection）？**

| 需求 | 集中式 | 分布式 |
|------|--------|--------|
| 频繁更新/删除 | ❌ 复杂（按 id 删点） | ✅ 简单（删 collection） |
| 论文数量 ≥ 2000 | ❌ 单 collection 过大 | ✅ 天然隔离 |
| 多模态资源 | ❌ 混在一起 | ✅ 按类型隔离 |
| 知识图谱扩展 | ❌ 需要重构 | ✅ Collection 作为节点 |

**最终选择：分布式**

---

## 常用命令

### 后端

```bash
cd backend

# 安装依赖
uv sync

# 启动服务
uv run python main.py

# 或直接用 uvicorn
uv run uvicorn app.main:app --reload

# 单元测试（纯逻辑，无外部依赖）
uv run pytest tests/unit/ -v

# 集成测试（需真实 API）
uv run pytest tests/integration/ -v -s

# 全部测试
uv run pytest tests/ -v
```

### 测试目录规范

```
tests/
├── unit/          # 单元测试（每次提交）
├── integration/   # 集成测试（合并前/手动）
├── fixtures/      # 测试输入（只读）
├── output/        # 测试产出（.gitignore）
└── _legacy/       # 旧代码（不运行）
```

详细规范见 `backend/tests/README.md`。

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

---

## 配置管理

所有配置通过 `.env` 文件管理：

```env
# Kimi Coding API（VLM + LLM）
KIMI_API_KEY=your_key
KIMI_BASE_URL=https://api.kimi.com/coding/v1

# 硅基流动（Embedding + Rerank）
SILICONFLOW_API_KEY=your_key

# 固定模型契约（不可更改）
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B
EMBEDDING_DIMENSIONS=1536
RERANK_MODEL=Qwen/Qwen3-Reranker-8B

# 切分策略参数
CHUNK_MAX_CONTEXT=32000
CHUNK_TARGET_SIZE=24000
CHUNK_OVERLAP_BUFFER=8000
```

**配置约束**：
- 更换 Embedding/Rerank 模型会导致向量库失效，需要重建索引
- 这些是"系统硬约束"，防止模型漂移污染索引

---

## 🔮 未来扩展标注规范

所有未来扩展点在代码中用 `🔮 未来扩展` 标记：

```python
async def retrieve(
    query: str,
    resource_types: list[str] | None = None,  # 🔮 未来扩展：用户自选数据类型
    selected_papers: list[str] | None = None,  # 🔮 未来扩展：用户自选文献
) -> dict[str, Any]:
    """
    ═════════════════════════════════════════════════════════════════════
    🔮 未来扩展：Collection 过滤逻辑
    ═════════════════════════════════════════════════════════════════════

    # 实现代码写在这里

    产品价值：
    - 提高准确性：用户知道答案在哪些文献里
    - 增强掌控感：用户主动选择
    - 减少干扰：排除不相关文献
    """
```

**快速定位所有扩展点**：
```bash
grep -r "🔮 未来扩展" app/
```

---

## 已知问题与限制

### 已修复
- [x] PDF 解析：从本地 PyMuPDF 改为 MinerU API
- [x] 向量库：从 zvec（RocksDB）改为 Chromadb（SQLite），根治 Windows 锁问题
- [x] Redis 依赖：移除 Redis，对话历史迁移到 SQLite
- [x] 切分策略：实现混合语义切分
- [x] VLM/LLM 接口：添加抽象层，可替换实现
- [x] RRF 融合：Dense + BM25 融合检索
- [x] 导入备份：每阶段持久化，支持断点续传
- [x] PDF 引用跳转：WPS API 打开 PDF
- [x] 自动标题生成：LLM 生成对话标题
- [x] 容灾降级：错误分类、重试策略、VLM 降级

### 待完成
- [ ] 用户自选文献功能（接口已预留）
- [ ] 多模态资源支持（视频、文档、笔记）
- [ ] 知识图谱集成
- [ ] Rerank 启用（当前未启用）

---

## 参考实现

- Novel_Agents RAG 工具: `D:/真项目/Novel_Agents/.tools/rag`
- z_ai-mcp-server: `D:/开发区/L2Demo/z_ai-mcp-server-0.1.3`
