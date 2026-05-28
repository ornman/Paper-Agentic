# cleaning 模块审计

## 对照模块
- 设计：`preprocessing/cleaning/`
- 代码：`backend/app/data_layer/preprocessing/cleaning/markdown_cleaner.py`

## 结论
- 文本规整逻辑有基础可用性，但当前实现只完成了一半职责。

## 发现
- [P1] 模块没有产出设计文档要求的 `structured JSON`。
  - 证据：`markdown_cleaner.py:24-29` 的 `CleaningResult` 只有 `markdown/stats/logs`；`clean_markdown():85-89` 也只返回这三项。
  - 影响：`document_id`、`anchors`、`visual_blocks`、`stats.anchor_count` 等设计字段完全没有来源。

- [P2] “全角半角统一”只处理数字和英文字母，没有处理标点。
  - 证据：`markdown_cleaner.py:125-144`
  - 影响：设计文档要求统一数字和标点，但当前输出对中文全角标点无效。

- [P2] 标题标准化只处理“向下跳级”，没有补充标题路径、原层级信息等后续 chunking 需要的数据。
  - 证据：`markdown_cleaner.py:147-173`
  - 影响：后续无法构造 `heading_path` 和更稳定的结构锚点。

## 建议
1. 把 cleaning 拆成“文本清洗”和“结构化投影”两步，输出统一的 cleaned markdown + structured payload。
2. 在这里就把 heading path、图片占位、visual seed 信息准备好，减轻 chunking/VLM 的补丁式工作。

