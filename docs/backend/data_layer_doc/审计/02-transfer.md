# transfer 模块审计

## 对照模块
- 设计：`preprocessing/transfer/`
- 代码：`backend/app/data_layer/preprocessing/transfer/pipeline.py`

## 结论
- 这是当前预处理层最核心、也是问题最集中的模块。
- Route A 可以部分走通；Route B/C/D 在 VLM 入口就会炸；cleaning 和 chunking 之间的数据交接也没有闭合。

## 发现
- [P0] VLM 调用入口不存在，带图片路由会在运行时直接失败。
  - 证据：`pipeline.py:260-263` 从 `..vlm_understanding` 导入 `process_images`；`vlm_understanding/__init__.py:10-26` 没有导出该函数，模块内部也只有 `VLMProcessor.process_images()` 方法。
  - 复现：`uv run python - <<...>>` 导入 `process_images` 直接报 `ImportError`。
  - 影响：Route B/C/D 的真实链路不可能通过。

- [P0] cleaning/VLM 的输出没有进入 chunking，chunking 仍在消费原始 markdown。
  - 证据：`pipeline.py:226-253` 只 `gather` 结果，不保存清洗结果、不合并 VLM 描述；`pipeline.py:270-277` 仍然对 `conversion_result.markdown` 做 chunking。
  - 影响：设计文档中的“clean -> vlm 回填 -> chunk”顺序完全没有生效。

- [P1] 路由决策没有真实使用 probe 全量结果。
  - 证据：`pipeline.py:190-196` 把 `has_text_layer=True`、`has_table_signals=False` 写死。
  - 影响：表格类 PDF、伪文本 PDF、扫描件边缘场景会被系统性误路由。

- [P1] 状态机没有实现设计文档里的 `retrying`，降级也没有真正改变状态。
  - 证据：`PipelineStage` 只定义了 `QUEUED/PROBING/ROUTING/TRANSFORMING/CLEANING/VLM_ENRICHING/CHUNKING/DONE/FAILED/DEGRADED`；`pipeline.py:249-253` 只发 `pipeline.degraded` 事件，没有把 `state.stage` 改成 `DEGRADED`。
  - 影响：上层无法通过状态机可靠分辨“成功但降级”和“完全成功”。

- [P1] 监控事件命名与设计不一致，且粒度过粗。
  - 证据：`pipeline.py:242` 发的是 `vlm.started`，设计文档要求的是 `vlm.image.started / completed / failed`。
  - 影响：后续即使接入 monitor，也无法按图片粒度定位慢点和失败点。

## 建议
1. 先补一个统一的 `process_images()` 适配层，或让 orchestrator 显式实例化 `VLMProcessor`。
2. 在 state 中显式保存 `probe_result`、`cleaning_result`、`vlm_result`、`final_markdown`、`chunks`。
3. 让路由只基于 `ProbeResult`，不要硬编码布尔值。
4. 把降级和重试建模成真实状态，而不是只打一条日志。

