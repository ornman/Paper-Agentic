# 后端测试规范

## 目录结构

```
tests/
├── conftest.py              # 根配置（sys.path）
├── .gitignore               # 排除 data/ fixtures/ _artifacts/ __pycache__/
│
├── agent_layer/             # Agent 层测试
│   ├── unit/                # 单测（纯逻辑，mock 外部依赖）
│   │   ├── contracts/       # 数据契约测试
│   │   ├── hooks/           # Hook 测试
│   │   ├── orchestration/   # 编排测试
│   │   ├── planning/        # 规划测试
│   │   ├── response/        # 回答生成测试
│   │   ├── runtime/         # 运行时测试
│   │   ├── session/         # 会话测试
│   │   └── chain/           # 多组件串联测试（全 mock）
│   ├── e2e/                 # 端到端测试
│   └── soak/                # 压力测试
│
├── data_layer/              # 数据层测试
│   ├── unit/                # 纯逻辑单测
│   │   ├── chroma_store/    # 向量库 + BM25 测试
│   │   ├── chunking/        # 语义切分测试
│   │   ├── cleaning/        # 清洗测试
│   │   ├── config_embedding/ # 配置 + embedding 测试
│   │   ├── document_service/ # 文档服务测试
│   │   ├── file_management/  # 文件管理测试
│   │   ├── preprocessor_monitor/ # 监控测试
│   │   ├── probe/           # 探针测试
│   │   ├── retrieval/       # 检索测试
│   │   ├── transfer/        # 路由调度测试
│   │   ├── mineru_processing/ # MinerU 解析测试
│   │   └── vlm_understanding/ # VLM 测试
│   └── integration/         # 集成测试（需真实 API / 文件）
│
├── service_layer/           # 服务层测试
│   └── unit/                # 纯逻辑单测
│
├── fixtures/                # 测试输入（只读，不修改，不入库）
│   └── README.md
│
└── data/                    # 测试产出（.gitignore，不入库）
```

> **PDF 测试样本**统一放在项目根目录 `datasets/` 下（`中文文献-测试-PDF/`、`外文文献-测试-PDF/`），
> 集成测试通过相对路径 `../../datasets/` 引用，不再在 tests/ 内维护副本。
```

## 分类原则

| 类型 | 目录 | 特征 | 运行频率 |
|------|------|------|----------|
| 单元测试 | `{layer}/unit/` | 纯逻辑，mock 外部依赖，毫秒级 | 每次提交 |
| 集成测试 | `{layer}/integration/` | 需要真实 API / 真实文件，秒~分钟级 | 合并前 / 手动 |
| 端到端测试 | `{layer}/e2e/` | 全链路流程验证 | 发布前 |
| 压力测试 | `{layer}/soak/` | 大量数据 / 长时间运行 | 定期 |

## 运行命令

```bash
cd backend

# 运行所有单元测试
uv run pytest tests/agent_layer/unit tests/data_layer/unit tests/service_layer/unit -v

# 运行所有集成测试
uv run pytest tests/data_layer/integration -v -s

# 运行特定模块
uv run pytest tests/data_layer/unit/cleaning/ -v

# 运行全部（不含 soak/e2e）
uv run pytest tests/agent_layer/unit tests/data_layer tests/service_layer -v
```

## 添加新测试

1. 判断所属 layer：`agent_layer` / `data_layer` / `service_layer`
2. 判断类型：纯逻辑 → `unit/`，需 API → `integration/`，全链路 → `e2e/`
3. 放到对应子目录，保持 `test_<module>.py` 命名
4. 共享 fixtures 写在对应 `conftest.py`
5. 测试产出写入 `data/`（不要写到 fixtures/ 或其他目录）

## PDF 样本

- `fixtures/pdfs_zh/` — 中文论文
- `fixtures/pdfs_en/` — 英文论文
- 这些文件不入库，自行准备
- 新增样本直接放入对应目录即可

## 不入库的内容

| 目录/文件 | 原因 |
|-----------|------|
| `fixtures/pdfs_*/` | PDF 体积大（500MB+），自行准备 |
| `data/` | MinerU 解析产物，运行时生成 |
| `_artifacts/` | soak reports、fault logs，运行时产物 |
| `__pycache__/` | Python 字节码 |
