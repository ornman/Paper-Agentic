# MVP 后端设计文档

**日期**: 2026-03-25
**状态**: 已确认
**适用范围**: `D:/同步/project/MVP/backend`

---

## 1. 目标与边界

本次后端重构的目标，是把当前已经偏离需求的 FastAPI 后端，收敛为一个**可控、可调试、可扩展**的模块化单体系统，为 WPS 插件提供稳定的论文辅助写作能力。

本轮设计只覆盖后端 MVP，边界如下：

- **部署形态**：纯本地单机 MVP
- **前端形态**：WPS 插件前端，轮询 Word/WPS 文档内容
- **问答形态**：确定性工作流，不做真 Agent tool-calling
- **PDF 处理主链路**：只走 MinerU API
- **索引模式**：只做两种
  - 暴力切分（brute）
  - 父子块检索（parent_child）
- **检索形态**：HyBriD（向量 + BM25）+ 重排序
- **回答要求**：必须标注来源，至少到段落级

不在本轮 MVP 范围内的内容：

- 远端服务化部署
- Word/PPT 等非 PDF 文档清洗
- 真 Agent 自主工具决策
- 多级递归检索
- 复杂统计学习型断层识别

---

## 2. 总体架构

后端采用**模块化单体（Modular Monolith）**。

特点：

- 运行上是一个本地 FastAPI 服务
- 代码上按业务领域拆模块，而不是把所有 service / repository / model 混堆
- 模块之间只通过明确的 service / DTO / repository 边界通信
- 路由层不允许直接跨层拼接业务逻辑

### 2.1 核心模块

| 模块 | 职责 |
|------|------|
| `session` | 会话管理、消息历史、来源回写 |
| `library` | 文档库元数据、文档列表、删除、重建入口 |
| `ingestion` | PDF 路径校验、MinerU 调用、结果拉取、清洗编排 |
| `indexing` | chunk 生成、双索引模式、Embedding、Chroma、BM25 |
| `retrieval` | 场景识别、Query Rewrite、加权召回、融合、Rerank、断层截断 |
| `qa` | 场景提示词、上下文拼装、DeepSeek 调用、SSE 输出 |

### 2.2 调用边界

允许的调用关系：

- `api routes -> application service`
- `library -> ingestion / indexing`
- `qa -> retrieval`
- `retrieval -> rewrite / hybrid / rerank`
- `indexing -> embedding / vector repo / bm25 repo`
- `session` 只管会话，不直接碰索引层

不允许：

- 路由直接调仓储做复杂业务
- 问答逻辑直接绕过 retrieval 读取 Chroma
- ingestion 直接操作会话层
- retrieval 直接改写数据库状态

---

## 3. 前端与后端的状态边界

WPS 轮询缓存属于**前端运行态数据**，不是后端持久化状态。

### 3.1 输入原则

前端负责提供：

- `text`：轮询缓存的文档内容
- `user_text`：圈选文本
- `user_prompt`：用户输入提示词

后端负责：

- 场景识别
- Query Rewrite
- 检索召回
- 重排序
- DeepSeek 生成
- 引用来源返回

### 3.2 状态约束

- 后端**不长期保存**轮询缓存 `text`
- 关闭 Word/WPS 后，相关运行态内容由前端自然失效
- 后端只保存正式聊天消息与引用结果，不保存 Word 临时全文缓存

这样可以避免前后端双缓存导致的数据脏状态。

---

## 4. 四种问答场景与工作流编排

后端按字段存在性做确定性路由。

### 4.1 场景 1：只有轮询缓存

输入：

- `text` 有值
- `user_text` 为空
- `user_prompt` 为空

权重：

- `text = 100%`

用途：

- 用户点击“灵感”按钮
- 重点是给启发、角度、结构建议，不直接代写正文

### 4.2 场景 2：轮询缓存 + 圈选文本

输入：

- `text` 有值
- `user_text` 有值
- `user_prompt` 为空

权重：

- `text = 30%`
- `user_text = 70%`

### 4.3 场景 3：轮询缓存 + 圈选文本 + 用户提示词

输入：

- `text` 有值
- `user_text` 有值
- `user_prompt` 有值

权重：

- `text = 20%`
- `user_text = 40%`
- `user_prompt = 40%`

### 4.4 场景 4：只有用户提示词

输入：

- `text` 为空
- `user_text` 为空
- `user_prompt` 有值

权重：

- `user_prompt = 100%`

---

## 5. Query Rewrite 与检索流程

### 5.1 Rewrite 原则

每个输入源**单独改写**，不先拼成一个大 query。

即：

- `text` 单独 rewrite
- `user_text` 单独 rewrite
- `user_prompt` 单独 rewrite

原因：

1. 三类输入语义职责不同，先混合会污染意图
2. 便于按权重分配召回配额
3. 便于调试哪一路 rewrite 出问题

### 5.2 单路检索流程

对每个输入源都执行同样的流程：

1. 原始输入文本
2. Query Rewrite
3. 构造检索 query
4. 向量检索
5. BM25 检索
6. 融合得到该输入源候选结果列表

### 5.3 召回规模

每一路先独立召回：

- `top_k = 8 ~ 15`
- 默认配置先取 `12`

### 5.4 加权配额

假设最终候选池目标大小为 `N`。

#### 场景 2

- `text = round(N * 0.3)`
- `user_text = round(N * 0.7)`

#### 场景 3

- `text = round(N * 0.2)`
- `user_text = round(N * 0.4)`
- `user_prompt = round(N * 0.4)`

#### 配额补偿

如果某一路有效结果不足：

- 剩余额度由其他输入源按得分高低补齐

### 5.5 断层截断

原则：

- 宁滥勿缺，但出现明显断层时，只保留断层前结果

MVP 先用简单阈值法：

- 计算相邻结果分数差
- 若下降比例超过阈值，则视为断层
- 只保留断层前结果

断层截断发生在：

- 单路召回完成后
- 权重配额分配前

### 5.6 全局排序

每一路按权重取出候选后：

1. 汇总所有候选 chunk
2. 去重（同 chunk 只保留最高分）
3. 执行全局 Rerank
4. 得到最终上下文列表

因此：

- 权重决定谁更容易进入候选池
- 最终排序由全局 Rerank 决定

---

## 6. PDF 导入与清洗主链路

正式导入链路固定为：

`前端传本地 PDF 路径`
→ `library 创建导入任务`
→ `ingestion 调 MinerU API`
→ `拿到 JSON 结果`
→ `正则/规则清洗噪音`
→ `规范化结构`
→ `indexing 按索引模式建索引`
→ `更新文档状态`

### 6.1 导入任务状态机

建议状态：

- `pending`
- `parsing`
- `cleaning`
- `indexing`
- `completed`
- `failed`
- `deleting`
- `deleted`

并记录：

- `error_stage`
- `error_message`

这样前端可以直接知道失败点在哪一层。

### 6.2 清洗原则

清洗目标不是重新发明 PDF 解析器，而是把 MinerU 输出收敛为 RAG 友好的结构。

默认清除：

- 页眉
- 页脚
- 连续页码
- 孤立 DOI / ISSN / 收稿日期等噪点
- 乱码和碎公式片段
- 重复块
- 过短无语义价值块
- 参考文献区（默认不进主正文索引，可后续单独处理）

默认保留：

- 标题
- 各级小标题
- 正文段落
- 表格文本结果
- 图片说明文字
- 摘要 / 结论等与主题高度相关内容

### 6.3 规范化结构

内部统一转换成三层：

#### Document

- `document_id`
- `title`
- `file_path`
- `index_mode`
- `created_at`

#### ParentBlock

- `parent_id`
- `document_id`
- `section_title`
- `content`
- `page_start`
- `page_end`
- `order_index`

#### ChildChunk

- `chunk_id`
- `parent_id`
- `document_id`
- `content`
- `page`
- `paragraph_id`
- `token_count`

最终回答引用最少落在 `ChildChunk` 级别。

---

## 7. 双索引模式

### 7.1 模式一：暴力切分（brute）

规则：

- 按 token 近似长度切块
- 每块目标约 `500 ~ 1000 tokens`
- 超出则均匀切分
- 邻接块首尾重叠

特点：

- 快
- 简单
- 效果一般

前端需要提示：

- “速度快，但语义边界较粗，效果较弱”

### 7.2 模式二：父子块检索（parent_child）

这是 MVP 主打模式。

思路：

- 父块保存较完整的语义上下文
- 子块作为主检索单元
- 检索时优先召回子块，再反挂父块补上下文

MVP 优先采用：

- **子召回后回挂父**

原因：

- 子块命中更精确
- 最终引用也需要落在段落 / 子块级
- 父块更适合作为上下文补充而不是主命中单元

### 7.3 超长块处理

如果块内容超过 `32k` 上下文阈值：

- 不直接入库
- 均匀切分为约 `24k`
- 相邻块首尾重叠

这是索引层通用保护规则，防止异常超长块污染后续 embedding / rerank / prompt 注入。

---

## 8. 存储与检索基础设施

### 8.1 向量库

使用：

- `ChromaDB`

写入字段：

- `id`
- `embedding`
- `document`
- `metadata`

metadata 至少包含：

- `document_id`
- `document_title`
- `index_mode`
- `layer`
- `parent_id`
- `page`
- `paragraph_id`

### 8.2 关键词检索

使用：

- `rank_bm25`
- `jieba`

BM25 侧也必须保存：

- `id`
- `tokenized_text`
- `raw_text`
- `metadata`

BM25 不是辅助玩具，而是 HyBriD 的一半。

---

## 9. 模型、外部工具与知识源基线

### 9.1 WPSJS / 官方 API 信息源

涉及以下问题时：

- WPSJS
- WPS 插件 API
- WPS 事件系统
- Word / WPS 轮询相关细节
- DeepSeek 官方 API 文档
- MinerU 官方说明
- 硅基流动接口说明

优先使用本地 micro-rag 工具：

- `D:/同步/.tools/rag`

不默认依赖训练数据对小众 API 的记忆。

### 9.2 Embedding 硬约束

固定为：

- `EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B`
- `EMBEDDING_DIMENSIONS=1536`

这是硬约束，不允许漂到 4096。

### 9.3 Rerank 硬约束

固定为：

- `RERANK_MODEL=Qwen/Qwen3-Reranker-8B`

### 9.4 主问答模型

固定为：

- DeepSeek 官方 API

环境变量占位：

- `DEEPSEEK_BASE_URL`
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_MODEL=deepseek-chat`

### 9.5 角色分工

- DeepSeek：Query Rewrite / 问答生成
- SiliconFlow：Embedding / Rerank
- MinerU：PDF -> JSON 解析

---

## 10. API 设计

### 10.1 API 分组

- `/api/v1/session`
- `/api/v1/library`
- `/api/v1/query`
- `/api/v1/config`

### 10.2 主问答接口

`POST /api/v1/query/ask`

请求体：

```json
{
  "session_id": "sess_xxx",
  "text": "前端轮询缓存，可为空",
  "user_text": "圈选文本，可为空",
  "user_prompt": "用户提示词，可为空",
  "index_mode": "brute|parent_child",
  "top_k": 12
}
```

行为：

- 识别场景
- 单路 rewrite
- 加权召回
- HyBriD + Rerank
- DeepSeek 生成带来源回答
- SSE 返回

### 10.3 纯检索接口

`POST /api/v1/query/retrieve`

用途：

- 调试检索链路
- 向前端返回 rewrite / 召回 / rerank 中间结果

### 10.4 文档导入接口

`POST /api/v1/library/import`

请求体：

```json
{
  "file_path": "D:/xxx/论文.pdf",
  "index_mode": "brute|parent_child",
  "tags": ["城乡治理", "公共文化"]
}
```

### 10.5 文档列表接口

`GET /api/v1/library/documents`

返回：

- 文档状态
- 索引模式
- 错误信息
- 创建时间等元数据

### 10.6 文档删除接口

`DELETE /api/v1/library/documents/{document_id}`

行为：

- 标记 `deleting`
- 删除 Chroma 条目
- 删除 BM25 条目
- 删除相关中间缓存
- 成功后置为 `deleted`

### 10.7 文档重建接口

`POST /api/v1/library/documents/{document_id}/reindex`

用途：

- 不重新导入 PDF
- 基于现有 PDF / 解析结果重建索引

---

## 11. SSE 事件设计

固定事件类型：

- `retrieval_start`
- `retrieval_done`
- `chunk`
- `sources`
- `done`
- `error`

### 11.1 示例

```text
event: retrieval_start
data: {"scene":"scene_3"}

event: retrieval_done
data: {"count":8}

event: chunk
data: {"content":"从现有研究看，", "index":0}

event: sources
data: {
  "sources": [
    {
      "source_id": 1,
      "document_title": "公共数字文化服务效能的关键影响因素及其机理研究",
      "page": 12,
      "paragraph_id": "p_12_03",
      "snippet": "公共数字文化服务效能受..."
    }
  ]
}

event: done
data: {"total_tokens":1234}
```

---

## 12. 数据模型建议

### 12.1 DocumentRecord

- `document_id`
- `title`
- `file_path`
- `index_mode`
- `status`
- `tags`
- `created_at`
- `updated_at`
- `error_stage`
- `error_message`

### 12.2 RetrievedChunk

- `chunk_id`
- `parent_id`
- `document_id`
- `document_title`
- `page`
- `paragraph_id`
- `content`
- `vector_score`
- `bm25_score`
- `fusion_score`
- `rerank_score`

### 12.3 RewriteResult

- `source_type`
- `original_text`
- `rewritten_query`

---

## 13. 错误处理原则

必须把错误当作带上下文的事件，而不是一句“内部错误”。

### 13.1 对前端

前端应能知道：

- 哪个操作失败
- 失败在哪个阶段
- 下一步是否可重试

### 13.2 对后端

后端记录：

- `stage`
- `document_id`
- `session_id`
- `request_id`
- 上游响应摘要
- 异常栈

### 13.3 Embedding 维度守卫

系统启动、建索引、执行检索时都必须验证：

- 当前模型是否为 `Qwen/Qwen3-Embedding-8B`
- 当前维度是否为 `1536`

若不一致：

- 拒绝建索引
- 拒绝检索
- 返回明确错误

---

## 14. 测试策略

### 14.1 单元测试

覆盖：

- 场景判定
- 权重配额
- 断层截断
- chunk 路由
- 引用格式化
- 状态机迁移

### 14.2 集成测试

覆盖：

- `library -> ingestion -> indexing`
- `query ask -> retrieval -> qa`
- `delete document -> vector/bm25 cleanup`

### 14.3 端到端测试

最少三条：

1. PDF 导入闭环
2. 场景 3 问答闭环
3. 删除闭环

---

## 15. 目录重构建议

建议重构为：

```text
backend/app/
├── api/
│   └── v1/routes/
│       ├── session.py
│       ├── library.py
│       ├── query.py
│       └── config.py
├── core/
│   ├── config.py
│   ├── errors.py
│   └── logging.py
├── modules/
│   ├── session/
│   ├── library/
│   ├── ingestion/
│   ├── indexing/
│   ├── retrieval/
│   └── qa/
└── main.py
```

原则：

- 保留 FastAPI 壳
- 重写偏离需求的业务层
- 吸收底层可复用仓储思路
- 彻底移除“PyMuPDF 自研链路为主”的旧假设

---

## 16. 最终结论

本次 MVP 后端重构的最终共识如下：

- 本地单机 MVP
- 模块化单体
- MinerU 是唯一 PDF 主链路
- 双索引模式：`brute` + `parent_child`
- 四种问答场景固定编排
- 前端持有 WPS 轮询缓存，后端只消费
- DeepSeek 负责主问答
- SiliconFlow 负责 Embedding + Rerank
- Embedding 维度固定为 `1536`
- 涉及 WPSJS / 官方 API 时优先查本地 micro-rag 工具

这份文档是当前后端设计的唯一有效结果，后续实施以此为准。
