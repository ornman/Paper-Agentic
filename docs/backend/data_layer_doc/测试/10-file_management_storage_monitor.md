# file_management 与 storage_monitor 模块测试设计

## 目标
- 验证真实产物目录、备份、加载、监控报告是否闭环。

## 用例
1. `FILE-U01`：`create_document_dirs/copy_paper/save_markdown/load_markdown/save_structured/save_report/backup_document` 的定向单测。
2. `FILE-C01`：拿 transformation + cleaning + chunking 的真实产物执行保存，再从磁盘重载验证一致性。
3. `FILE-C02`：验证 `delete_document()` 与 soft delete 的协同策略；当前允许先固定“未协同”的问题。
4. `SMON-U01`：`record_latency/update_health/get_latency_stats/save_report` 的单测。
5. `SMON-C01`：在真实 embedding/chroma/bm25 跑完后刷新 `StorageMonitor`，要求落盘报告里有真实数值。

## ClaudeCode 执行要求
- 测试文件建议：
  - `backend/tests/data_layer/file_management/test_directory_manager.py`
  - `backend/tests/data_layer/monitor/test_storage_monitor.py`
- 真实链路产物要来自前置模块测试，不要人工造最小 JSON 冒充全流程结果。

