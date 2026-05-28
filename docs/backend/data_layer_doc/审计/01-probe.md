# probe 模块审计

## 对照模块
- 设计：`preprocessing/probe/`
- 代码：`backend/app/data_layer/preprocessing/probe/pdf_probe.py`

## 结论
- 本模块本身未发现“导入即炸”的阻断错误。
- 主要问题不在探针实现本身，而在探针输出没有被 `transfer` 完整消费，导致探针价值在下游被削弱。

## 发现
- [P1] `ProbeResult` 中的关键信号没有进入调度状态机。
  - 证据：`pdf_probe.py:82-127` 已计算 `recommended_route`、`has_table_signals`、`page_count`、`doc_complexity_level`；`transfer/pipeline.py:173-176,190-196` 只保留了 `has_images`、`has_form_fields`、`has_formula_signals`、`is_scan_like`，并把 `has_text_layer`/`has_table_signals` 写死。
  - 影响：probe 即使判对了复杂度和路由，真实调度仍可能错路。

- [P2] `recommended_route` 在 probe 里和 transfer 里各算一遍，形成双重真相源。
  - 证据：`pdf_probe.py:93-102` 与 `transfer/pipeline.py:190-197` 都在做路由决策。
  - 影响：后续规则一旦修改，很容易出现 probe 与 orchestrator 结果不一致，但日志又看不出谁是权威。

## 建议
1. 让 `transfer` 直接消费 `ProbeResult` 全量结构，避免重新拼布尔值。
2. 保留一个唯一的路由决策入口；要么 probe 只产信号、transfer 决策，要么 transfer 只信任 probe 的推荐路由。

