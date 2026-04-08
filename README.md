# WPS 论文写作辅助工具

基于私有文献知识库的论文写作辅助工具，以 WPS 插件形式嵌入写作场景。

## 目录结构

```
D:/同步/
├── docs/                  # 🌐 北极星（全局方向）
│   ├── 北极星.md           # 愿景、定位、阶段规划
│   ├── 账单/              # 经费记录
│   ├── picture/           # 图片资源
│   └── plans/             # 全局计划
│
├── project/               # 📦 当前阶段：MVP
│   ├── docs/              # MVP 详细设计（模块级）
│   │   ├── 00-overview/   # 架构总览
│   │   ├── 10-api/        # API 层
│   │   ├── 20-workflows/  # 工作流层
│   │   ├── 30-services/   # 服务层
│   │   ├── 40-repositories/ # 仓储层
│   │   ├── 50-clients/    # 外部客户端
│   │   └── mvp/           # MVP 原始文档
│   ├── frontend-prototype/# UI 演示版
│   └── wps-thesis-mvp/    # 真实开发版（待建）
│
├── research/              # 📚 调研资料
│   ├── notes/             # 调研笔记
│   └── references/        # 参考项目
│
└── .tools/                # 🔧 辅助工具
    ├── rag/               # 微 RAG 知识库
    └── wps-debug/         # WPS 调试系统
```

### 文档演进

```
北极星（全局方向）
    │
    └── MVP ──→ 初期 ──→ 中期 ──→ 后期 ──→ 打磨 ──→ 上线
           │
           └── 每阶段独立的 docs，基于全局 + 上一阶段
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

### 文档分类

| 文档类型 | 放置位置 | 说明 |
|----------|----------|------|
| 全局文档 | `docs/` | 跨项目的公共文档（账单、计划等） |
| 阶段文档 | `project/docs/` | 特定开发阶段的技术文档 |
| 项目文档 | `project/<项目名>/docs/` | 项目内部的详细文档 |

### 新增内容

| 内容类型 | 放置位置 |
|----------|----------|
| 技术文档 | `project/docs/` |
| 测试数据 | `project/data/` |
| 调研笔记 | `research/notes/` |
| 参考项目 | `research/references/` |
| 开发工具 | `.tools/<工具名>/` |
| 经费账单 | `docs/账单/` |

### 路径管理

所有工具路径在 `config.py` 中统一管理，禁止硬编码。
