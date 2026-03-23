# WPS 论文写作辅助工具

基于私有文献知识库的论文写作辅助工具，以 WPS 插件形式嵌入写作场景。

## 目录结构

```
D:/同步/
├── project/           # 核心交付物（可独立打包）
│   ├── docs/          # 技术文档
│   │   └── mvp/       # MVP 阶段文档
│   └── data/          # 测试数据
│       └── papers/    # 测试论文
│
├── research/          # 调研资料（可归档）
│   ├── notes/         # 调研笔记
│   └── references/    # 参考项目
│
└── .tools/            # 辅助工具（不提交 Git）
    ├── rag/           # 微 RAG 知识库
    └── wps-debug/     # WPS 调试系统
```

## 快速开始

### 查看技术文档

核心设计文档位于 `project/docs/mvp/` 目录。

### 使用 RAG 知识库

```bash
cd .tools/rag
python scripts/query.py "你的问题"
```

## 开发说明

详见 `CLAUDE.md`（内部开发文档）。

## 规范

### 新增内容

| 内容类型 | 放置位置 |
|----------|----------|
| 技术文档 | `project/docs/` |
| 测试数据 | `project/data/` |
| 调研笔记 | `research/notes/` |
| 参考项目 | `research/references/` |
| 开发工具 | `.tools/<工具名>/` |

### 路径管理

所有工具路径在 `config.py` 中统一管理，禁止硬编码。
