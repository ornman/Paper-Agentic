# transfer 模块测试设计

## 目标
- 验证 orchestrator 的状态机、路由消费、降级逻辑。
- 在真实 PDF 上至少跑通 Route A；对 B/C/D/E 则要先复现当前缺陷，再在修复后转绿。

## 用例
1. `TRANSFER-U01`：直接测试 `decide_route()` 的 A/B/C/D/E 判定矩阵。
2. `TRANSFER-I01`：用 monkeypatch 替换 probe/transformation/cleaning/vlm/chunking，验证 `run()` 的阶段推进、事件记录、失败分支和降级分支。
3. `TRANSFER-C01`：选 1 份中文 Route A + 1 份英文 Route A 真实样本跑 orchestrator，断言最终 `stage == DONE`，且 chunk 结果非空。
4. `TRANSFER-C02`：选 1 份 B/C/D 路由真实样本，当前应复现 `process_images` 导入失败；修复后应验证 cleaning 与 VLM 输出已进入 chunking。
5. `TRANSFER-C03`：选 1 份 E 路由真实样本，当前应复现 OCR unsupported；修复后应验证降级或 OCR 输出路径。

## ClaudeCode 执行要求
- 测试文件建议：`backend/tests/data_layer/transfer/test_pipeline.py`
- Route B/C/D/E 用例在修复前允许红灯，但不允许直接 `xfail` 永久跳过。
- 真链路回归时要把 `PipelineState.events` 落盘，便于比对 monitor 行为。

