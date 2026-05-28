# data_layer 架构设计

## 1. 文档定位

这份文档是 data_layer 层的唯一活动架构文档。

它定义：

1. data_layer 的三层子架构
2. 每个子模块的职责、输入输出、内部类型
3. 层间 IO 约定
4. 并发模型与调度策略
5. 监控与日志策略

旧文档已归档至 `__achive__/`，不再作为活动设计来源。

---

## 2. 总体架构

```text
data_layer/
├── preprocessing/          # 预处理层
│   ├── probe/                      # ① 探针：PDF 特征检测
│   ├── transfer/                   # ② 路由 + 调度：engine + scheduler
│   ├── transformation/             # ③ 转换：PDF → markdown + json + 图片
│   ├── cleaning/                   # ④ 清洗：格式规范化、去噪
│   ├── vlm_understanding/          # ⑤ VLM：图片/表单/公式语义理解
│   ├── chunking/                   # ⑥ 切分：语义切分 + 锚点生成
│   └── monitor/                    # 监控：进度、日志、耗时
│
├── storage/               # 持久化层
│   ├── embedding/                  # 向量化：文本 → 向量
│   ├── config/                     # 配置：读取用户/系统配置
│   ├── chroma_store/               # 向量库：增删改查 + 软删除
│   ├── file_management/            # 文件管理：PDF/图片/产物目录
│   └── monitor/                    # 监控：延迟、存储健康、日志
│
└── retrieval/                      # 检索层
    ├── dense/                      # 向量检索
    ├── sparse/                     # BM25 关键词检索
    └── fusion/                     # RRF 融合 + rerank
```

### 三层关系

```text
                   ┌─────────────────────────────────────────────┐
                   │              Agent 层（调用方）               │
                   └──────────┬──────────────────┬───────────────┘
                              │ retrieve()       │
                              ▼                  │
                   ┌──────────────────────┐      │
                   │      retrieval       │      │
                   │  dense + sparse +    │      │
                   │      fusion          │      │
                   └──────────┬───────────┘      │
                              │ 读取索引          │
                              ▼                  │
                   ┌──────────────────────┐      │
                   │   storage   │      │
                   │  embedding + chroma  │      │
                   │  + file_management   │      │
                   └──────────┬───────────┘      │
                              │ 读取产物文件      │
                              ▼                  │
                   ┌──────────────────────┐      │
                   │ preprocessing│      │
                   │  probe → transfer →  │      │
                   │  transform → clean → │      │
                   │  vlm → chunk         │      │
                   └──────────────────────┘      │
                              │                   │
                              ▼                   │
                        [产物落盘] ───────────────┘
```

### 核心设计原则

1. **层间隔离**：三层各有各的 IO，不共享 Python 类型。层间传递靠数据格式（文件/JSON/ChromaDB）。
2. **故障隔离**：预处理炸了，持久化里有数据，检索照样跑。
3. **每层自监控**：monitor 子模块贯穿每层。
4. **transfer 是预处理层的调度中枢**：类似 Scrapy 的 engine + scheduler 复合体。

---

## 3. 预处理层详细设计

### 3.1 probe/

**职责**：对 PDF 做轻量特征检测，输出特征类型。

**输入**：
- PDF 文件路径（支持批量）

**输出**：
- ProbeResult：PDF 特征数据

**ProbeResult 字段**：

| 字段 | 类型 | 说明 |
|---|---|---|
| page_count | int | 页数 |
| has_text_layer | bool | 是否有文字层 |
| text_density | float | 每页平均字符数 |
| is_scan_like | bool | 是否疑似扫描件 |
| has_images | bool | 是否有图片 |
| image_count | int | 图片数量 |
| has_form_fields | bool | 是否有表单字段 |
| form_field_count | int | 表单字段数量 |
| has_formula_signals | bool | 是否有公式信号 |
| formula_signal_score | float | 公式信号强度 0-1 |
| has_table_signals | bool | 是否有表格信号 |
| table_signal_score | float | 表格信号强度 0-1 |
| doc_complexity_level | str | simple / moderate / complex |

**检测手段**：

| 检测项 | 工具 | 方法 |
|---|---|---|
| 文字层 | pypdf | extract_text()，总字符 > 100 = 有文字层 |
| 文字密度 | pypdf | 总字符 / 页数 |
| 扫描件 | pypdf | text_density < 50 且 page_count > 2 |
| 图片 | pdfplumber | page.images 计数 |
| 表单字段 | pypdf | reader.get_fields() |
| 公式信号 | pdfplumber + 正则 | 数学符号密度 + LaTeX 痕迹 + 公式关键词 |
| 表格信号 | pdfplumber + 正则 | 表格关键词 + 列对齐检测 |

**参考实现**：`reference/external/anthropic-skills/pdf/scripts/`

---

### 3.2 transfer/

**职责**：预处理层的调度中枢。接收 probe 输出，决定路由，编排整个 pipeline。

**输入**：
- ProbeResult（来自 probe）
- PDF 文件路径

**输出**：
- 调度各子模块执行
- 异常处理（降级 / 终止）
- 事件推送给 monitor

**路由决策**：

| 路由 | 条件 | transformation 策略 |
|---|---|---|
| A | 有文字层，无图片/表单/公式 | MarkItDown 主提取 |
| B | 有文字层 + 有图片 | MarkItDown + 页面转图 |
| C | 有文字层 + 表单/表格/公式 | MarkItDown + 表单提取 + 远程增强 |
| D | 结构复杂，多模态混合 | MarkItDown + 多工具组合 |
| E | 扫描件，几乎无文字层 | OCR API + VLM API |

**调度模式**：

主循环轮询各阶段状态，不阻塞：

```text
transfer 主循环：
  while pipeline 未完成:
    poll probe → 得到特征
    决定路由 → 启动 transformation
    poll transformation 产出：
      如果有图片 → 启动 vlm_understanding worker（就绪）
      如果有 markdown → 启动 cleaning worker
    poll cleaning + vlm_understanding：
      两者都完成 → 启动 chunking
    poll chunking → 完成 → 通知持久化层
```

**状态机**：

```text
queued → probing → routing → transforming → cleaning/vlm_enriching → chunking → done
                                              ↑                          │
                                              └──── 降级重试 ────────────┘
```

异常分支：
- `retrying`：瞬时错误，自动重试
- `degraded`：跳过非关键增强（如 VLM 失败），主链继续
- `failed`：不可恢复错误

---

### 3.3 transformation/

**职责**：根据 transfer 的路由决策，将 PDF 转换为 markdown + metadata + 图片。

**输入**：
- PDF 文件路径
- transfer 的路由决策（A/B/C/D/E）

**输出**：
- ConversionResult：markdown + metadata + 图片路径列表
- 处理日志

**ConversionResult 字段**：

| 字段 | 类型 | 说明 |
|---|---|---|
| markdown | str | 提取的 markdown 文本 |
| metadata | dict | 文件信息、探针数据、路由、复杂度 |
| images | list[dict] | [{"page": int, "path": str}] |
| success | bool | 是否成功 |
| error | str \| None | 失败原因 |

**并发模型**：

- **执行器**：ProcessPoolExecutor（CPU + 磁盘 IO 密集型，绕 GIL）
- **默认并发**：5 进程
- **自适应校准**：
  - 首次运行：默认 5 进程，测量每个文件耗时
  - 计算最优并发：`optimal = cores * (1 + wait_ratio)`
  - 下限 5，上限 `cores * 2`
  - 校准结果存 `_concurrency.json`
  - 后续运行直接读取已校准值
- **批量处理**：支持批量 PDF 输入，进程池并发转换

**实现参考**：`backend/tests/UnitTesting-Docling&&Anthropic'sPDF&DOCX/test_pdf_router.py`

---

### 3.4 cleaning/

**职责**：对 transformation 产出的 markdown 做格式清洗和规范化。

**输入**：
- ConversionResult（来自 transformation）

**输出**：
- 清洗后的 markdown
- structured JSON（统一产物）
- 处理日志

**清洗规则**：

| 规则 | 说明 |
|---|---|
| 去多余空白 | 连续空行合并、行尾空格清除 |
| 标题层级标准化 | 确保 heading 层级连续、无跳级 |
| 乱码碎片修复 | 检测并移除控制字符、乱码序列 |
| 语义断层修复 | 连续 6+ 换行合并、重复字符序列清除 |
| 全角半角统一 | 数字和标点统一为半角 |

**structured JSON 顶层结构**：

```json
{
  "document_id": "doc_xxx",
  "paper_id": "doc_xxx",
  "doc_type": "pdf",
  "source_file_path": "papers/demo.pdf",
  "pipeline_version": "v4",
  "markdown_path": "full.md",
  "images_dir": "images/",
  "doc_level": {
    "file_name": "demo.pdf",
    "page_count": 10,
    "route": "B",
    "char_count": 5000
  },
  "anchors": [],
  "visual_blocks": [],
  "stats": {
    "chunk_count": 5,
    "anchor_count": 0,
    "visual_block_count": 0
  }
}
```

---

### 3.5 vlm_understanding/

**职责**：对 transformation 产出的图片做 VLM 语义理解，生成描述并回填到 markdown。

**输入**：
- transformation 产出的图片文件（已提取好的，不是从 markdown 解析）
- cleaning 产出的清洗后 markdown（用于回填）

**输出**：
- 图片描述（写入临时 JSON）
- parent_anchor 绑定
- visual_blocks
- 回填后的最终 markdown

**异步流水线**：

```text
阶段 1（接收图片）：
  transfer 检测到有图片 → vlm worker 就绪
  接收 transformation 产出的图片文件列表

阶段 2（异步 VLM 调用）：
  逐张异步调用 VLM API（async/await，不是线程池并发）
  每张图的结果立即写入临时 JSON 文件
  JSON 格式：{image_path: {description, analysis_route, status, ...}}

阶段 3（回填）：
  等待 cleaning 完成
  读取临时 JSON 中的描述
  遍历清洗后 markdown，找到图片引用
  将描述回填为 [描述](图片路径) 格式
  生成 parent_anchor 和 visual_blocks
```

**analysis_route 枚举**：

| 值 | 含义 |
|---|---|
| general_image | 普通插图、照片 |
| technical_diagram | 架构图、流程图 |
| data_visualization | 折线图、柱状图、散点图 |
| form_like | 表单、问卷 |
| formula_like | 公式截图 |
| text_dense_visual | 高文字密度截图 |

**降级策略**：

- VLM 调用失败：自动重试 3 次（指数退避 + 抖动）
- 3 次仍失败：标记 `analysis_status = degraded`，生成兜底描述
- 兜底描述：`[此处包含一张图片，自动描述失败，建议结合原图查看。](images/xxx.jpg)`
- 不阻断主链

**VLM 配置**：

| 项 | 默认值 |
|---|---|
| API 地址 | https://api.coro0.top/v1 |
| 模型 | qwen3-vl:235b |
| 最大重试 | 3 |
| 退避策略 | 指数退避 + 随机抖动 |
| base_delay_ms | 1000 |
| jitter_ms | random(0, 300) |

---

### 3.6 chunking/

**职责**：将清洗后的 markdown 切分为语义完整的 chunk，生成锚点。

**输入**：
- 清洗后的 markdown
- structured JSON

**输出**：
- Chunk 列表（带锚点、父子块关系）

**切分方法**：基于嵌入向量的语义边界检测

```text
1. 按句子分割文本（nltk / spaCy / 正则）
2. 每个句子计算嵌入向量
3. 滑动窗口计算相邻句子余弦相似度
4. 相似度显著下降处 = 语义边界
5. 在边界附近找自然句子结束位置（句号、换行）切分
```

**约束**：

| 参数 | 值 |
|---|---|
| 最小 chunk | 128 token |
| 最大 chunk | 512 token |
| 相似度下降阈值 | 30%（相对前几个窗口平均值） |

**超大块处理**：

当单个语义块超过 embedding 模型上下文窗口的 1/4 时：
1. 退出纯语义切分
2. 暴力均分
3. 仅在此场景引入 overlap

**锚点字段**：

| 字段 | 说明 |
|---|---|
| anchor_id | 锚点唯一标识 |
| source_file_path | 原始文件路径 |
| doc_type | pdf / docx / doc / pptx / ppt / xlsx / xls（MinerU 支持的所有格式） |
| page | 页码（1-based） |
| block_id | 解析块标识 |
| block_type | paragraph / heading / table / formula / figure |
| heading_path | 标题层级路径 |
| paragraph_index | 段落序号 |
| char_start / char_end | 在 markdown 中的字符范围 |
| bbox | 可选，PDF 矩形坐标 |
| parent_anchor_id | 子块回指父块 |
| source_text_hash | 校验锚点是否与当前产物一致 |

**父子块策略**：

- 父块：正文或包含图片的语义块
- 子块：该图片对应的语义描述块
- 召回规则：父块被召回时，相关子块一并可用

---

### 3.7 monitor/（预处理层）

**职责**：全程监控预处理 pipeline 的执行状态。

**事件类型**：

| 事件 | 说明 |
|---|---|
| probe.started / completed | 探针开始/完成 |
| routing.decision | 路由决策结果 |
| transformation.started / completed / failed | 转换开始/完成/失败 |
| cleaning.started / completed | 清洗开始/完成 |
| vlm.image.started / completed / failed | 单张图 VLM 开始/完成/失败 |
| chunking.started / completed | 切分开始/完成 |
| pipeline.completed / failed | 整个 pipeline 完成/失败 |
| pipeline.degraded | 降级事件 |

**日志字段**：

| 字段 | 说明 |
|---|---|
| timestamp | 事件时间 |
| level | 日志级别 |
| event | 事件名 |
| task_id | 导入任务标识 |
| stage | 当前阶段 |
| duration_ms | 阶段耗时 |
| degraded | 是否降级 |
| error | 错误信息（如有） |

---

## 4. 持久化层详细设计

### 4.1 embedding/

**职责**：将文本转换为向量。

**输入**：
- Chunk 列表

**输出**：
- 向量列表

**实现**：
- 硅基流动 API（Qwen3-Embedding-8B，1536 维）
- 支持批量处理 + 并发控制
- 自动重试（3 次，指数退避）

---

### 4.2 config/

**职责**：读取用户配置和系统默认配置。

**默认配置**：

| 项 | 默认值 |
|---|---|
| VLM API 地址 | https://api.coro0.top/v1 |
| VLM 模型 | qwen3-vl:235b |
| Embedding API 地址 | 硅基流动 |
| Embedding 模型 | Qwen3-Embedding-8B |
| Embedding 维度 | 1536 |
| Rerank 模型 | Qwen3-Reranker-8B |

**来源**：
- 前端传递的用户配置（覆盖默认值）
- `.env` 文件
- 系统默认值

---

### 4.3 chroma_store/

**职责**：向量库的增删改查，软删除策略。

**CRUD 操作**：

| 操作 | 说明 |
|---|---|
| insert | 写入 chunk 向量 + metadata |
| query | 向量相似度检索 |
| delete_paper | 软删除：标记 deleted_at |
| cleanup | 启动时检查，超过 7 天的软删除数据真正删除 |

**软删除策略**：

```text
删除时：
  不真正删除 ChromaDB 数据
  在 JSON 文件（soft_delete_records.json）中记录 deleted_at 时间戳

启动时：
  检查所有软删除记录
  deleted_at 超过 7 天 → 真正删除 ChromaDB 数据
  deleted_at 未超过 7 天 → 保留（可恢复）
```

---

### 4.4 file_management/

**职责**：管理文档文件、图片、产物的目录结构和生命周期。

**目录结构**：

```text
data/
├── papers/           # 原始文件副本
│   └── {doc_id}/
│       └── *.pdf / *.docx / *.doc / *.pptx / *.ppt / *.xlsx / *.xls
├── parsed/           # 解析产物
│   └── {doc_id}/
│       ├── markdown.json
│       ├── structured.json
│       ├── extraction_report.json
│       └── images/
│           ├── page_1.png
│           └── ...
├── chroma_db/        # 向量索引
├── bm25_index/       # 关键词索引
└── backups/          # 导入中间产物和恢复点
```

---

### 4.5 monitor/（持久化层）

**职责**：监控持久化层的运行状态。

**监控项**：

| 项 | 说明 |
|---|---|
| embedding 延迟 | 单次 / 批量 embedding 耗时 |
| chroma 写入延迟 | 单次 upsert 耗时 |
| chroma 查询延迟 | 单次 query 耗时 |
| 存储健康 | ChromaDB 文档数、BM25 索引大小 |
| 磁盘占用 | papers/ parsed/ 目录大小 |

---

## 5. 检索层详细设计

### 5.1 dense/

**职责**：向量相似度检索。

**输入**：query 向量 + topk + 可选 paper_ids
**输出**：Doc 列表（id + content + metadata）

### 5.2 sparse/

**职责**：BM25 关键词检索。

**输入**：query 文本 + topk + 可选 paper_ids
**输出**：(doc_id, score) 列表

**实现**：jieba 分词 + rank_bm25

### 5.3 fusion/

**职责**：融合 dense + sparse 结果。

**输入**：dense 结果 + sparse 结果 + topk
**输出**：融合后的 Doc 列表

**算法**：RRF（Reciprocal Rank Fusion）

```text
score(doc) = Σ 1 / (k + rank_i)

其中 k = 60（RRF 常数）
```

---

## 6. 层间 IO 约定

层与层之间不共享 Python 类型，靠 IO 格式传递：

| 交接点 | 方向 | 格式 |
|---|---|---|
| 预处理 → 持久化 | 写 | `data/parsed/{doc_id}/` 下的文件 |
| 持久化 → 检索 | 读 | ChromaDB + BM25 索引 |
| 检索 → Agent 层 | 调用 | 函数返回值（Doc 列表） |
| API → transfer | 调用 | 文件路径 + 配置参数 |

**产物文件格式**：

| 文件 | 内容 |
|---|---|
| markdown.json | 清洗后的 markdown 全文 |
| structured.json | 锚点 + visual_blocks + 统计 |
| extraction_report.json | 路由、工具、降级、耗时 |
| images/ | 提取的图片文件 |

---

## 7. 与现有代码的映射

| 现有文件 | 新位置 | 处理方式 |
|---|---|---|
| `conversion/pdf_probe.py` | `preprocessing/probe/` | 搬迁，基本可用 |
| `conversion/pdf_router.py` | `preprocessing/transformation/` | 拆分：路由逻辑移入 transfer，转换逻辑保留 |
| `conversion/markitdown_adapter.py` | `preprocessing/transformation/` | 搬迁 |
| `conversion/docling_adapter.py` | 删除 | 死代码，Docling 不是当前默认链 |
| `normalization/vision_model.py` | `preprocessing/vlm_understanding/` | 重写为完整 pipeline |
| `chunking/semantic_chunker.py` | `preprocessing/chunking/` | 增强：加锚点、加嵌入相似度切分 |
| `indexing/embedding_client.py` | `storage/embedding/` | 搬迁 |
| `storage/vector_index.py` | `storage/chroma_store/` + `retrieval/dense/` | 拆分：写入 vs 查询 |
| `storage/keyword_index.py` | `storage/chroma_store/` + `retrieval/sparse/` | 拆分：写入 vs 查询 |
| `storage/sqlite_runtime.py` | `storage/chroma_store/` | 保留 library_items / import_tasks，conversation 迁移到 Agent 层 |
| `retrieval/fusion.py` | `retrieval/fusion/` | 搬迁 |
| `contracts/*` | 各层内部自定义 | 不再共享，删除 contracts/ |

---

## 8. 仍待落地的事项

- [x] DOCX 支持（MinerU 原生支持 docx/doc/pptx/xlsx，同级 pipeline）
- [ ] Rerank 接入（检索层后续增强）
- [ ] OCR 增强（vlm_understanding 后续扩展）
- [ ] 知识图谱集成
