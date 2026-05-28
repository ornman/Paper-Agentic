# chroma_store 模块测试设计

## 目标
- 验证本地向量库、BM25、软删除在真实链路产物上的行为。

## 用例
1. `STORE-U01`：`SoftDeleteManager.mark_deleted()` 的 Windows 路径回归测试，固定当前 `Path + ".tmp"` 问题。
2. `STORE-U02`：`KeywordIndex` 在 1/2/3 篇文档语料上的查询行为，要求至少返回最佳匹配。
3. `STORE-I01`：用真实 chunk + 真实 embedding 向量插入 `VectorIndex`，再 query/delete。
4. `STORE-I02`：验证 `cleanup_expired()` 在向量库/关键词库删除部分成功时的持久化行为。
5. `STORE-I03`：`VectorIndex.close()` 后释放文件句柄，Windows 临时目录能成功清理。

## ClaudeCode 执行要求
- 测试文件建议：
  - `backend/tests/data_layer/chroma_store/test_soft_delete.py`
  - `backend/tests/data_layer/chroma_store/test_keyword_index.py`
  - `backend/tests/data_layer/chroma_store/test_vector_index.py`
- `STORE-I01` 不能只用假向量；至少要接一次真实 embedding 产物。

