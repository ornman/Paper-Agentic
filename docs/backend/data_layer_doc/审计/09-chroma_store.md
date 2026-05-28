# chroma_store 模块审计

## 对照模块
- 设计：`storage/chroma_store/`
- 代码：
  - `backend/app/data_layer/storage/chroma_store/vector_index.py`
  - `backend/app/data_layer/storage/chroma_store/keyword_index.py`
  - `backend/app/data_layer/storage/chroma_store/soft_delete.py`

## 结论
- 这里既有可直接复现的 Windows 路径 bug，也有真实检索质量问题。

## 发现
- [P0] `SoftDeleteManager.mark_deleted()` 在 Windows 上直接报错。
  - 证据：`soft_delete.py:146-150` 把 `Path` 与字符串直接做 `+ ".tmp"`。
  - 复现：真实运行报 `TypeError: unsupported operand type(s) for +: 'WindowsPath' and 'str'`。
  - 影响：软删除从第一步就不可用。

- [P1] `KeywordIndex.query()` 会把小语料库命中结果全部过滤掉。
  - 证据：`keyword_index.py:69-86` 最终只返回 `score > 0` 的结果；在 2 篇和 3 篇文档样本下实测查询都返回空列表。
  - 影响：单篇论文检索、早期库容量检索基本不可用。

- [P1] `VectorIndex.close()` 没有真正释放底层 Chroma 资源。
  - 证据：`vector_index.py:40-42` 只把引用设为 `None`。
  - 复现：在 Windows 临时目录里 `init()` 后即使调用 `close()`，退出时仍会因为 `chroma.sqlite3` 被占用而清理失败。
  - 影响：测试清理、临时库、并发重建都容易挂。

- [P2] 软删除策略和设计文档不一致。
  - 证据：设计要求 SQLite 记录和 7 天恢复窗口；当前实现只有 `soft_delete_records.json`，且没有 restore API。
  - 影响：恢复能力和事务一致性都较弱。

## 建议
1. 先修 `Path.with_suffix()`/字符串拼接问题，让软删除能跑起来。
2. 调整 BM25 返回规则，不要简单用 `score > 0` 作为唯一阈值。
3. 为 VectorIndex 增加真实的资源释放策略，并把它纳入测试清理规范。

