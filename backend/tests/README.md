# 后端测试规范

## 目录结构

```
tests/
├── conftest.py              # 根配置（sys.path）
├── .gitignore               # 忽略 output/
│
├── unit/                    # 单元测试（纯逻辑，无外部依赖）
│   └── data_layer/          # 数据层单元测试
│       ├── conftest.py      # 共享 fixtures（tmp_dir, zh_pdf, en_pdf）
│       ├── cleaning/
│       ├── chunking/
│       ├── probe/
│       ├── config_embedding/
│       ├── file_management/
│       ├── preprocessor_monitor/
│       ├── retrieval/
│       ├── transfer/
│       ├── transformation/
│       ├── vlm_understanding/
│       └── chroma_store/
│
├── integration/             # 集成测试（需真实 API / 文件）
│   └── data_layer/
│       ├── test_mineru_json_analysis.py    # MinerU JSON 元数据分析（中英文）
│       ├── test_mineru_comparison.py       # MinerU 解析对比
│       └── test_real_api.py                # 真实 API 测试
│
├── fixtures/                # 测试输入（只读，不修改）
│   ├── pdfs_zh/             # 中文 PDF 样本
│   └── pdfs_en/             # 英文 PDF 样本
│
└── output/                  # 测试产出（.gitignore，不入库）
    └── mineru_json_analysis/
        ├── zh/              # 中文 PDF 解析结果
        │   ├── <tag>/
        │   │   ├── full.md
        │   │   ├── content_list.json
        │   │   ├── model.json
        │   │   └── layout.json
        │   └── ...
        └── en/              # 英文 PDF 解析结果
            ├── <tag>/
            │   └── ...
            └── ...
```

## 分类原则

| 类型 | 目录 | 特征 | 运行频率 |
|------|------|------|----------|
| 单元测试 | `unit/` | 纯逻辑，mock 外部依赖，毫秒级 | 每次提交 |
| 集成测试 | `integration/` | 需要真实 API / 真实文件，秒~分钟级 | 合并前 / 手动 |

## 运行命令

```bash
cd backend

# 运行所有单元测试
uv run pytest tests/unit/ -v

# 运行所有集成测试
uv run pytest tests/integration/ -v -s

# 运行特定模块
uv run pytest tests/unit/data_layer/cleaning/ -v

# 运行全部
uv run pytest tests/ -v
```

## 添加新测试

1. 判断类型：纯逻辑 → `unit/`，需 API → `integration/`
2. 放到对应子目录，保持 `test_<module>.py` 命名
3. 共享 fixtures 写在对应 `conftest.py`
4. 测试产出写入 `output/`（不要写到 fixtures/ 或其他目录）

## PDF 样本

- `fixtures/pdfs_zh/` — 中文论文（政策文件、学术论文、技术研究）
- `fixtures/pdfs_en/` — 英文论文
- 这些文件是只读的，不要修改或删除
- 新增样本直接放入对应目录即可

## 注意事项

- 不要在 tests/ 根目录散落测试文件
- 不要把测试产出提交到 git（output/ 已 gitignore）
- 集成测试需要真实 API key，CI 环境可能跳过
- 旧测试代码已归档至 `_archive/02-旧数据/backend_tests_legacy/`
