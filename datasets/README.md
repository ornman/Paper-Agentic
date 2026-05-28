# 测试样本

本目录用于存放批量导入和端到端测试所需的 PDF 文件。

**测试 PDF 不纳入版本控制**，请自行准备论文样本。

## 使用方式

将 PDF 文件直接放入本目录或子目录即可：

```text
datasets/
├── 中文论文/
│   └── *.pdf
├── 英文论文/
│   └── *.pdf
└── README.md
```

### 批量导入

```bash
uv run python scripts/batch_import.py --dir ../datasets
```

也可通过环境变量指定：

```bash
BATCH_IMPORT_DIR=/path/to/pdfs uv run python scripts/batch_import.py
```
