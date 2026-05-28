# file_management 与 storage_monitor 模块审计

## 对照模块
- 设计：`storage/file_management/`、`storage/monitor/`
- 代码：
  - `backend/app/data_layer/storage/file_management/directory_manager.py`
  - `backend/app/data_layer/storage/monitor/storage_monitor.py`

## 结论
- 两个模块各自能做局部工作，但都还没有接进真实数据链路。

## 发现
- [P1] `DirectoryManager` 的保存接口没有被预处理 pipeline 或持久化写入链路实际调用。
  - 证据：代码搜索只命中了 `directory_manager.py` 自身定义，没有看到 `save_markdown()/save_structured()/save_report()` 的实际使用点。
  - 影响：设计文档要求的 `data/parsed/{doc_id}/` 产物目录当前不会自动生成。

- [P1] `StorageMonitor` 也没有接到真实读写路径上。
  - 证据：代码搜索只命中了 `storage_monitor.py` 自身定义和 `data_layer/__init__.py` 暴露，没有看到 `record_latency()/update_health()` 的调用。
  - 影响：embedding、chroma 写入、chroma 查询、BM25 查询的延迟监控当前没有真实数据。

- [P2] `delete_document()` 是硬删除，和 soft delete 策略没有协同。
  - 证据：`directory_manager.py:184-199`
  - 影响：如果调用顺序不当，文件产物可能先于索引恢复窗口被彻底删掉。

## 建议
1. 把 `DirectoryManager` 接到 preprocess -> persistence 交接点。
2. 把 `StorageMonitor` 包进 embedding/vector/bm25 的真实调用路径，而不是留作孤立工具类。

