# PDF 导入流程设计（修正版）

## 设计缺陷（2026-03-24）

### 错误 1：Embedding 维度错误

**问题**：测试时误将 EMBEDDING_DIMENSION 从 1536 改为 4096  
**后果**：向量空间稀疏，检索质量下降  
**修正**：改回 1536，清空重建索引  

### 错误 2：OCR 模型名称错误

**问题**：`.env` 中 `OCR_MODEL=deepseek-ai/deepseek-vl2`  
**正确**：`OCR_MODEL=deepseek-ai/DeepSeek-OCR`  
**修正**：已修改配置  

### 错误 3：没有中间缓存和断点续传

**问题**：
1. 清洗完直接入库，失败了就全丢
2. 没有断点续传，大批量导入中途失败得从头开始
3. 没有错误隔离，一个 PDF 失败会影响整个批次

**正确设计**（见下方）

---

## 重新设计：三阶段导入流程

### 阶段 1：清洗 → JSON 缓存

```
PDF 输入 → PyMuPDF 解析 → 清洗（去页眉页脚）→ 输出 JSON
                ↓
         data/cache/{pdf_name}.json
```

**JSON 格式**：
```json
{
  "document_id": "xxx",
  "source_file": "path/to/pdf",
  "page_count": 10,
  "paragraphs": [
    {
      "id": "para_001",
      "content": "...",
      "page": 1,
      "bbox": [100, 200, 500, 400],
      "type": "paragraph"
    }
  ],
  "metadata": {
    "title": "文档标题",
    "created_at": "2026-03-24T12:00:00",
    "status": "cleaned"  // cleaned | embedding | indexed | failed
  }
}
```

### 阶段 2：向量化 → 批量 Embedding

```
读取 JSON → 批量 Embedding（32个/批）→ 更新 JSON
                ↓
         data/cache/{pdf_name}.json (status=embedding)
```

**错误处理**：
- 单个批次失败 → 重试 3 次
- 仍然失败 → 标记 `status=failed`，记录错误原因
- 继续处理下一个文档

### 阶段 3：入库 → ChromaDB + BM25

```
读取 JSON (status=embedding) → 写入 ChromaDB + BM25 → 更新 JSON
                ↓
         data/cache/{pdf_name}.json (status=indexed)
```

**幂等性**：
- 如果 `status=indexed`，跳过
- 如果 `status=failed`，可手动重试
- 支持删除重建（先删旧索引，再入库）

---

## 断点续传机制

### 扫描缓存目录

```python
def scan_cache_status(cache_dir: Path) -> dict:
    """扫描缓存目录，统计各状态文档数"""
    return {
        "cleaned": 10,     # 已清洗，待向量化
        "embedding": 5,    # 已向量化，待入库
        "indexed": 80,     # 已入库
        "failed": 1,       # 失败
    }
```

### 续传策略

```python
def resume_ingest():
    """从断点继续导入"""
    # 1. 扫描缓存
    status = scan_cache_status()
    
    # 2. 处理 failed（重试）
    for doc in get_docs_by_status("failed"):
        retry_ingest(doc)
    
    # 3. 处理 cleaned（向量化）
    for doc in get_docs_by_status("cleaned"):
        generate_embeddings(doc)
    
    # 4. 处理 embedding（入库）
    for doc in get_docs_by_status("embedding"):
        index_to_db(doc)
```

---

## 错误隔离

### 单文档失败不影响批次

```python
async def batch_ingest(pdf_paths: list[str]):
    """批量导入，错误隔离"""
    results = {
        "success": [],
        "failed": [],
    }
    
    for pdf_path in pdf_paths:
        try:
            doc_id = await ingest_single_pdf(pdf_path)
            results["success"].append(doc_id)
        except Exception as e:
            logger.error(f"导入失败: {pdf_path}, 原因: {e}")
            results["failed"].append({
                "path": pdf_path,
                "error": str(e),
            })
    
    return results
```

### 失败重试

```python
async def retry_failed():
    """重试所有失败的文档"""
    failed_docs = get_docs_by_status("failed")
    
    for doc in failed_docs:
        # 读取错误原因
        error = doc["metadata"]["error"]
        logger.info(f"重试: {doc['source_file']}, 原错误: {error}")
        
        try:
            # 从头开始重试
            await ingest_single_pdf(doc["source_file"])
        except Exception as e:
            # 仍然失败，更新错误信息
            doc["metadata"]["error"] = str(e)
            doc["metadata"]["retry_count"] += 1
            save_cache(doc)
```

---

## 缓存文件结构

```
data/
├── cache/                    # 清洗缓存（JSON）
│   ├── doc_001.json         # status: indexed
│   ├── doc_002.json         # status: failed
│   └── doc_003.json         # status: cleaned
├── chroma/                   # ChromaDB 向量库
│   └── chroma.sqlite3
├── bm25_index.json          # BM25 索引
└── app.db                   # SQLite（会话/消息）
```

---

## API 接口设计

### 1. 单文档导入

```http
POST /api/v1/ingest/
{
  "file_path": "path/to/pdf",
  "document_id": "optional_custom_id"
}

Response:
{
  "code": 0,
  "data": {
    "task_id": "xxx",
    "status": "cleaned"  // cleaned | embedding | indexed | failed
  }
}
```

### 2. 批量导入

```http
POST /api/v1/ingest/batch
{
  "directory": "path/to/pdfs",
  "recursive": true
}

Response:
{
  "code": 0,
  "data": {
    "task_id": "xxx",
    "total": 100,
    "queued": 100
  }
}
```

### 3. 查看导入状态

```http
GET /api/v1/ingest/status

Response:
{
  "code": 0,
  "data": {
    "cleaned": 10,
    "embedding": 5,
    "indexed": 80,
    "failed": 1,
    "total": 96
  }
}
```

### 4. 重试失败

```http
POST /api/v1/ingest/retry

Response:
{
  "code": 0,
  "data": {
    "retried": 1,
    "success": 1,
    "failed": 0
  }
}
```

---

## 下一步实现

1. ✅ 修正 Embedding 维度（实际为 4096，非 1536）
2. ✅ 修正 OCR 模型名称
3. ✅ 修正 import bug（pymupdf → fitz）
4. ✅ 清空旧索引，重建
5. ✅ 实现三阶段导入流程（9/9 PDF 全部成功）
6. ✅ 验证向量检索 + BM25 检索
7. ⏳ 接入 RAG 到问答流程
8. ⏳ 批量导入全部 PDF（约 86 个）

