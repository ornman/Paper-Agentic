# probe 模块测试设计

## 目标
- 验证 probe 在真实中英文 PDF 上能稳定输出完整特征。
- 为后续 transformation/transfer/vlm/chunking 测试生成 route 样本清单。

## 用例
1. `PROBE-U01`：不存在路径、非 PDF 路径应分别抛 `FileNotFoundError` / `ValueError`。
2. `PROBE-I01`：对 5 份中文 + 5 份英文真实 PDF 跑 `probe_pdf()`，校验 `ProbeResult` 字段完整、类型正确、`recommended_route in {"A","B","C","D","E"}`。
3. `PROBE-I02`：扫描全部 154 份 PDF，生成 `sample_manifest.json`，字段至少包含 `file_path/route/complexity/page_count/has_images/has_table_signals/has_formula_signals/is_scan_like`。
4. `PROBE-I03`：按 manifest 为每种可用 route 选至少 2 份代表样本，写入 `route_selection.json` 供后续模块复用。

## ClaudeCode 执行要求
- 测试文件建议：`backend/tests/data_layer/probe/test_pdf_probe.py`
- 产物建议：
  - `backend/tests/_artifacts/data_layer/sample_manifest.json`
  - `backend/tests/_artifacts/data_layer/route_selection.json`
- 通过标准：probe 不能只在小样本上通过；必须对全量样本扫描成功，最多允许个别损坏 PDF 被单独记录为异常样本。

