# 测试样本

本目录存放集成测试和批量导入所需的 PDF 文件。

**测试 PDF 不纳入版本控制**，请自行准备论文样本。

## 目录结构

```text
datasets/
├── 中文文献-测试-PDF/    # 中文论文 PDF
│   └── <论文主题>/
│       └── *.pdf
├── 外文文献-测试-PDF/    # 外文论文 PDF
│   └── *.pdf
└── README.md
```

## 使用方式

### 集成测试

`backend/tests/data_layer/integration/` 中的测试会自动扫描本目录。

### 批量导入

```bash
uv run python scripts/batch_import.py --dir ../datasets
```

也可通过环境变量指定：

```bash
BATCH_IMPORT_DIR=/path/to/pdfs uv run python scripts/batch_import.py
```
