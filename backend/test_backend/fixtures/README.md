# 测试数据目录

本目录用于存放集成测试和端到端测试所需的 PDF 文件。

**PDF 测试数据不纳入版本控制**，请自行准备。

## 使用方式

1. 在 `pdfs_en/` 放入英文论文 PDF
2. 在 `pdfs_zh/` 放入中文论文 PDF
3. 运行测试时通过环境变量 `TEST_FIXTURES_DIR` 指向本目录

```bash
TEST_FIXTURES_DIR=backend/test_backend/fixtures pytest backend/test_backend/integration/
```

## 目录约定

```
fixtures/
├── pdfs_en/    # 英文论文 PDF（自行准备）
├── pdfs_zh/    # 中文论文 PDF（自行准备）
└── README.md   # 本文件
```
