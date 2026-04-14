# 开发计划 — 2026-04-14

> 从勾子中的 ￥ 决策生成

---

## P0（必须做 - 阻断性问题）

### P0-1: Qdrant 索引写入失败回滚
**来源**: 勾子/5-哪里会断.md
**决策**: ￥同意1，简单，易于调试￥
**问题**: Embedding 失败时文档永久卡在 `indexing` 状态
**影响**: `app/modules/library/service.py:63-90`, `app/modules/ingestion/cleaning.py:38-108`
- [ ] 引入事务补偿：Embedding 失败时回退状态到 `pending` 并记录错误
- [ ] 测试：Embedding 失败后文档状态自动恢复

### P0-2: SQLite 并发写入冲突修复
**来源**: 勾子/5-哪里会断.md
**决策**: ￥1吧￥
**问题**: 并发导入多篇 PDF 时 SQLite 写锁冲突
**影响**: `app/repositories/sqlite_repo.py`, `app/main.py:47-52`
- [ ] 使用 `sqlalchemy.QueuePool` 配置连接池（`pool_size=5, max_overflow=10`）
- [ ] 配置 `check_same_thread=False`
- [ ] 测试：并发导入 3 篇 PDF 不冲突

### P0-3: 批量 Embedding 并发优化
**来源**: 勾子/5-哪里会断.md
**决策**: ￥同意￥
**问题**: 串行调用 Embedding API，100 篇 PDF 需 10 分钟
**影响**: `app/clients/embedding_client.py:29-51`, `app/core/config.py:124`
- [ ] 使用 `asyncio.gather()` 并发调用 `_embed_batch_raw()`
- [ ] 使用 `asyncio.Semaphore(5)` 控制并发数
- [ ] 测试：导入时间从 10 分钟降到 2 分钟

### P0-4: MinerU 轮询间隔优化
**来源**: 勾子/5-哪里会断.md
**决策**: ￥同意1￥
**问题**: 固定 5 秒轮询，导致检测延迟或误判超时
**影响**: `app/clients/mineru_client.py:29-52`, `app/core/config.py:140`
- [ ] 实现指数退避轮询：初始间隔 2 秒，失败后翻倍，上限 10 秒
- [ ] 修正超时判断逻辑，考虑网络延迟
- [ ] 测试：10 秒任务在 15 秒内检测完成

---

## P1（重要 - 稳定性）

### P1-1: 外部 API 降级策略
**来源**: 勾子/5-哪里会断.md
**决策**: ￥同意￥
**问题**: DeepSeek/SiliconFlow 故障导致全系统中断
**影响**: `app/clients/llm_client.py`, `app/clients/embedding_client.py`
- [ ] LLM 客户端添加超时配置
- [ ] Embedding 失败降级到 BM25 纯文本检索
- [ ] MinerU 超时后返回部分解析结果 + 错误提示

### P1-2: SSE 流式传输重连
**来源**: 勾子/5-哪里会断.md
**决策**: ￥同意￥
**问题**: 网络波动导致 SSE 断开，数据丢失
**影响**: `app/api/v1/routes/query.py:62-77`, `frontend/src/services/sse-client.ts`
- [ ] 后端 SSE 生成器捕获网络异常
- [ ] 前端实现指数退避重试（3 次，1s → 2s → 4s）
- [ ] 测试：网络中断后自动重连

### P1-3: BM25 索引更新修复
**来源**: 勾子/5-哪里会断.md
**决策**: ￥对，这个的确是缺陷，当初重构后就没管了￥
**问题**: 新增文档后 BM25 索引可能未更新
**影响**: `app/services/bm25_service.py`（需查找）
- [ ] 定位 BM25 索引更新代码
- [ ] 修复新增文档后索引不更新的问题
- [ ] 测试：新增文档后能被 BM25 检索到

### P1-4: 后端日志轮转
**来源**: 勾子/5-哪里会断.md
**决策**: 使用 `RotatingFileHandler`
**问题**: 长期运行后日志文件过大
**影响**: `app/core/logging_config.py`
- [ ] 添加 `RotatingFileHandler`（10MB，保留 5 个备份）
- [ ] 测试：日志文件自动轮转

---

## P2（优化 - 用户体验）

### P2-1: 文件路径校验改进
**来源**: 勾子/5-哪里会断.md
**决策**: ￥同意￥
**问题**: WSL 路径等格式被拒绝，无明确错误提示
**影响**: `app/modules/library/service.py:138-173`, `frontend/src/services/api-client.ts`
- [ ] 前端预校验文件路径格式
- [ ] 后端支持 WSL、Cygwin 路径格式
- [ ] 提供明确错误提示

### P2-2: SSE 缓冲区限制
**来源**: 勾子/5-哪里会断.md
**决策**: ￥同意1￥
**问题**: 高频发送 chunk 导致前端内存飙升
**影响**: `frontend/src/services/sse-client.ts:287-361`
- [ ] 设置 `buffer` 最大长度（10MB）
- [ ] 或使用流式解析（`TextDecoder` + `ReadableStream`）

---

## P3（延后 - 非紧急）

### P3-1: 前端会话状态持久化
**来源**: 勾子/5-哪里会断.md
**决策**: ￥同意2，这个之后再说￥
**问题**: 刷新页面后历史消息丢失
**影响**: `frontend/src/stores/conversation.ts`
- [ ] 使用 `localStorage` 持久化 `sessionId` 和 `messages`
- [ ] 或实现后端 `/api/v1/session/{session_id}` 接口

### P3-2: 前端错误监控
**来源**: 勾子/5-哪里会断.md
**决策**: ￥这个不着急。先做后端￥
**问题**: 生产环境错误无法追踪
**影响**: `frontend/src/main.ts`
- [ ] 集成前端错误监控（Sentry / 自建）

### P3-3: 前端 API 地址校验放宽
**来源**: 勾子/5-哪里会断.md
**决策**: ￥现在还在开发期，只有我能用￥
**问题**: Docker 容器部署时前端请求被拒绝
**影响**: `frontend/src/services/api-client.ts`
- [ ] 允许 `0.0.0.0` 作为开发环境地址

---

## 无需处理

### Qdrant 连接池配置
**来源**: 勾子/5-哪里会断.md
**决策**: ￥这个待会都重构了，不会高并发的￥
**说明**: 即将重构，无需处理

---

## 执行顺序

1. **P0-1** → **P0-2** → **P0-3** → **P0-4**（解决阻塞问题）
2. **P1-3** → **P1-4**（修复已知缺陷）
3. **P1-1** → **P1-2**（提升稳定性）
4. **P2-1** → **P2-2**（优化体验）
5. P3 延后处理
