# 预处理 monitor 模块测试设计

## 目标
- 验证 monitor 能记录阶段指标，并且真接到 orchestrator。

## 用例
1. `PMON-U01`：`start_task/start_stage/complete_stage/fail_stage/degrade_stage/complete_task/fail_task` 的定向单测。
2. `PMON-I01`：构建 orchestrator -> monitor adapter，验证 route A 样本跑完后能生成 metrics JSON。
3. `PMON-C01`：在真实 Route A 链路上校验事件序列和 duration 字段存在。
4. `PMON-C02`：在故障样本上验证失败事件与降级事件都能落盘。

## ClaudeCode 执行要求
- 测试文件建议：`backend/tests/data_layer/monitor/test_pipeline_monitor.py`
- 当前没有接线，因此 `PMON-I01/C01/C02` 应先红灯，再伴随接线修复一起转绿。

