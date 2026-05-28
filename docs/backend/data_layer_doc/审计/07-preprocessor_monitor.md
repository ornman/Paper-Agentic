# 预处理 monitor 模块审计

## 对照模块
- 设计：`preprocessing/monitor/`
- 代码：`backend/app/data_layer/preprocessing/monitor/pipeline_monitor.py`

## 结论
- monitor 类本身能写指标，但当前没有进入真实执行链路。

## 发现
- [P1] `PipelineMonitor` 没有被 `PipelineOrchestrator` 真正使用。
  - 证据：仓库搜索结果只看到 `data_layer/__init__.py` 暴露了 `PipelineMonitor`，没有看到任何 `start_task()/start_stage()/complete_task()` 的调用。
  - 影响：设计文档里的阶段耗时、降级事件、完成报告，在真实运行中不会落盘。

- [P1] orchestrator 的事件模型和 monitor API 没对齐。
  - 证据：`pipeline_monitor.py:56-166` 需要按 task/stage 显式 start/complete/fail；`transfer/pipeline.py` 只提供 `_emit()` 回调模型。
  - 影响：即使把 monitor 对象传进去，也需要额外适配器，否则拿不到结构化 metrics。

- [P2] 当前事件名与设计文档粒度不完全一致。
  - 证据：monitor 支持通用 stage 事件；design 要求 `vlm.image.started/completed/failed` 这类更细粒度事件。
  - 影响：后续定位图片级慢点会受限。

## 建议
1. 给 orchestrator 增加 monitor adapter，而不是只塞一个通用 callback。
2. 在 VLM 和 transformation 内部细化子任务事件，否则 monitor 只能看到大阶段。

