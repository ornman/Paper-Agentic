# 开发计划 — 2026-04-15

> 从勾子中的 ￥ 决策生成，包含完整上下文

---

## P0（必须做 - 阻断性问题）

### P0-1: Qdrant 索引写入失败回滚

**来源**: 勾子/5-哪里会断.md

**上下文（证据）**：
- `app/stores/qdrant_store.py`（未在本次读取中，需人工补充）— Qdrant 批量写入接口缺失
- `app/modules/library/service.py:63-90` — `import_pdf` 流程中，状态迁移到 `indexing` 后无回滚机制
- `app/modules/ingestion/cleaning.py:38-108` — 清洗阶段可能抛 `IndexingError`，但此时文档记录已是 `indexing` 状态

**问题（断点影响）**：
- 清洗成功 → 状态迁移到 `indexing` → Embedding 失败 → 文档永久卡在 `indexing` 状态
- 用户只能手动调用 `/api/v1/library/resume/{document_id}` 恢复（`service.py:92-128`）

**原因**：
当前设计中，状态迁移到 `indexing` 后如果 Embedding 失败，没有回滚机制，导致文档永久卡在中间状态。

**决策**：
同意1，简单，易于调试

**方案**：
引入事务补偿：Embedding 失败时回退状态到 `pending` 并记录错误

**影响文件**：
- `app/modules/library/service.py:63-90`
- `app/modules/ingestion/cleaning.py:38-108`

**检查清单**：
- [ ] 在 `import_pdf` 流程中添加异常捕获
- [ ] Embedding 失败时将状态回退到 `pending`
- [ ] 记录错误信息到文档记录
- [ ] 测试：Embedding 失败后文档状态自动恢复到 `pending`

---

### P0-2: SQLite 并发写入冲突修复

**来源**: 勾子/5-哪里会断.md

**上下文（证据）**：
- `app/repositories/sqlite_repo.py`（未在本次读取中，需人工补充）— SQLite 连接池配置缺失
- `app/main.py:47-52` — 启动时只触发 `get_engine()` 建表，未配置 `check_same_thread=False`
- `app/modules/library/repository.py` — 并发导入多篇 PDF 时可能触发 `sqlite3.ProgrammingError`

**问题（断点影响）**：
- 用户同时导入多篇 PDF → SQLite 写锁冲突 → 部分导入失败
- FastAPI 多 worker 模式下风险更高

**原因**：
SQLite 默认不支持多线程并发写入，需要配置连接池和线程检查参数。

**决策**：
1吧

**方案**：
使用 `sqlalchemy.QueuePool` 配置连接池（`pool_size=5, max_overflow=10`）

**影响文件**：
- `app/repositories/sqlite_repo.py`
- `app/main.py:47-52`

**检查清单**：
- [ ] 配置 `sqlalchemy.QueuePool`（`pool_size=5, max_overflow=10`）
- [ ] 配置 `check_same_thread=False`
- [ ] 测试：并发导入 3 篇 PDF 不冲突
- [ ] 测试：多 worker 模式下无写锁冲突

---

### P0-3: 批量 Embedding 并发优化

**来源**: 勾子/5-哪里会断.md

**上下文（证据）**：
- `app/clients/embedding_client.py:29-51` — `embed()` 方法按 `batch_size` 分批，但每批串行调用 `_embed_batch_raw()`
- `app/core/config.py:124` — `embedding_batch_size=32`，但未配置并发数
- `app/modules/library/service.py:63-90` — 导入多篇 PDF 时串行处理

**问题（断点影响）**：
- 导入 100 篇 PDF → Embedding 请求数 = `总chunk数 / 32`，若总 chunk 数 = 10000，则需 312 次串行 API 调用
- 每次调用假设 2 秒，总耗时约 624 秒（10 分钟）

**原因**：
当前实现中 `embed()` 方法按 `batch_size` 分批后，每批串行调用 `_embed_batch_raw()`，没有并发控制，导致大量时间浪费在等待 I/O 上。

**决策**：
同意

**方案**：
使用 `asyncio.gather()` 并发调用 `_embed_batch_raw()`，限制并发数（如 5）

**影响文件**：
- `app/clients/embedding_client.py:29-51`
- `app/core/config.py:124`

**检查清单**：
- [ ] 使用 `asyncio.gather()` 并发调用 `_embed_batch_raw()`
- [ ] 使用 `asyncio.Semaphore(5)` 控制并发数
- [ ] 在 `config.py:124` 添加并发数配置
- [ ] 测试：导入时间从 10 分钟降到 2 分钟

---

### P0-4: MinerU 轮询间隔优化

**来源**: 勾子/5-哪里会断.md

**上下文（证据）**：
- `app/clients/mineru_client.py:29-52` — 轮询间隔固定为 `settings.mineru_poll_interval=5` 秒（`config.py:140`）
- `app/clients/mineru_client.py:36-37` — 超时判断基于 `time.time() - start > timeout`，未考虑网络延迟

**问题（断点影响）**：
- MinerU 任务实际只需 10 秒完成，但固定轮询 5 秒间隔 → 可能需要 10-15 秒才能检测到完成
- MinerU 任务需要 290 秒（接近 300 秒超时），第 5 次轮询（25 秒）时误判为超时

**原因**：
固定轮询间隔导致：快速任务检测延迟，慢任务误判超时。未考虑网络延迟对超时判断的影响。

**决策**：
同意1

**方案**：
实现指数退避轮询：初始间隔 2 秒，每次失败后翻倍，上限 10 秒

**影响文件**：
- `app/clients/mineru_client.py:29-52`
- `app/core/config.py:140`

**检查清单**：
- [ ] 实现指数退避轮询逻辑
- [ ] 修正超时判断逻辑，考虑网络延迟
- [ ] 测试：10 秒任务在 15 秒内检测完成
- [ ] 测试：290 秒任务不会误判超时

---

## P1（重要 - 稳定性）

### P1-1: 外部 API 降级策略

**来源**: 勾子/5-哪里会断.md

**上下文（证据）**：
- `app/clients/llm_client.py:31-38` — LLM 调用无超时配置，直接 `await client.chat.completions.create()`
- `app/clients/embedding_client.py:87-101` — Embedding 客户端虽有 `timeout` 配置（`config.py:99` 设置 120 秒），但失败后完全依赖 `@retry_async` 重试，无降级
- `app/clients/mineru_client.py:29-52` — MinerU 轮询有超时（`config.py:141` 设置 300 秒），但超时后直接抛 `TimeoutError`，无降级
- `app/clients/kimi_client.py:297-298, 351-352` — Kimi API 调用硬编码 `timeout=120`，无动态配置

**问题（断点影响）**：
- DeepSeek API 故障 → 主问答链路完全中断
- SiliconFlow Embedding 失败 → 文献导入无法完成
- MinerU 超时 → PDF 解析卡死，用户看到无响应

**原因**：
外部 API 调用没有降级策略，一旦失败就完全中断服务。

**决策**：
同意

**方案**：
1. LLM 客户端添加超时配置
2. Embedding 失败降级到 BM25 纯文本检索
3. MinerU 超时后返回部分解析结果 + 错误提示

**影响文件**：
- `app/clients/llm_client.py`
- `app/clients/embedding_client.py`
- `app/modules/retrieval/service.py:52-56`

**检查清单**：
- [ ] LLM 客户端添加超时配置
- [ ] Embedding 失败时降级到 BM25
- [ ] MinerU 超时后返回部分结果
- [ ] 测试：API 故障时服务仍可用

---

### P1-2: SSE 流式传输重连

**来源**: 勾子/5-哪里会断.md

**上下文（证据）**：
- `app/api/v1/routes/query.py:62-77` — SSE 生成器未捕获 `httpx.RemoteProtocolError` / `ConnectionResetError`
- `frontend/src/services/sse-client.ts:374-394` — 前端发起请求后无重试机制，`response.ok` 为 false 时直接抛 `ApiClientError`
- `frontend/src/stores/conversation.ts:370-379` — `catch` 块只标记 `error` 状态，无重新请求逻辑

**问题（断点影响）**：
- 用户网络波动 → SSE 连接断开 → 已收到的 chunk 丢失，需手动刷新
- 后端进程重启 → 前端无法自动恢复，需用户重新触发

**原因**：
SSE 连接中断后没有自动重连机制，导致用户体验差、数据丢失。

**决策**：
同意

**方案**：
1. 后端 SSE 生成器捕获网络异常，返回 `{"type": "error", "data": {"message": "连接中断，请重试"}}`
2. 前端实现指数退避重试（3 次，间隔 1s → 2s → 4s），仅在 `ApiClientError.statusCode >= 500` 时触发

**影响文件**：
- `app/api/v1/routes/query.py:62-77`
- `frontend/src/services/sse-client.ts:374-394`
- `frontend/src/stores/conversation.ts:370-379`

**检查清单**：
- [ ] 后端 SSE 生成器捕获网络异常
- [ ] 前端实现指数退避重试
- [ ] 测试：网络中断后自动重连
- [ ] 测试：重连时保留已收到的 chunk

---

### P1-3: BM25 索引更新修复

**来源**: 勾子/5-哪里会断.md

**上下文（证据）**：
- 文件：`app/services/bm25_service.py`（未找到）
- 风险：新增文档后 BM25 索引可能未更新

**问题（断点影响）**：
新增文档后 BM25 索引可能未更新，导致检索不到新内容

**原因**：
当初重构后没管 BM25 索引更新逻辑，导致存在缺陷。

**决策**：
对，这个的确是缺陷，当初重构后就没管了

**方案**：
定位 BM25 索引更新代码并修复

**影响文件**：
- `app/services/bm25_service.py`（需先定位）

**检查清单**：
- [ ] 定位 BM25 索引更新代码
- [ ] 修复新增文档后索引不更新的问题
- [ ] 测试：新增文档后能被 BM25 检索到

---

### P1-4: 后端日志轮转

**来源**: 勾子/5-哪里会断.md

**上下文（证据）**：
- 文件：`app/core/logging_config.py`（未读取）
- 风险：长期运行后日志文件过大

**问题（断点影响）**：
长期运行后日志文件过大，占用磁盘空间

**原因**：
当前日志配置没有轮转机制，日志文件持续增长。

**决策**：
使用 `RotatingFileHandler`

**方案**：
添加 `RotatingFileHandler`（单文件最大 10MB，保留 5 个备份）

**影响文件**：
- `app/core/logging_config.py`

**检查清单**：
- [ ] 添加 `RotatingFileHandler`
- [ ] 配置 `maxBytes=10*1024*1024`
- [ ] 配置 `backupCount=5`
- [ ] 测试：日志文件自动轮转

---

## P2（优化 - 用户体验）

### P2-1: 文件路径校验改进

**来源**: 勾子/5-哪里会断.md

**上下文（证据）**：
- `app/modules/library/service.py:138-173` — `_validate_import_pdf_path()` 拒绝 URL / UNC 路径，但只检查 `file://` 和 `\\`
- `frontend/src/services/api-client.ts:225-242` — `importLibraryPdf()` 直接发送 `file_path`，未做前端校验

**问题（断点影响）**：
- 用户传入 `C:\\Users\\xxx\\test.pdf` → Windows 风格路径被接受
- 用户传入 `/mnt/c/Users/xxx/test.pdf`（WSL 路径）→ 可能被拒绝但无明确错误

**原因**：
文件路径校验逻辑不完整，只检查了部分格式，且前端没有预校验。

**决策**：
同意

**方案**：
1. 前端预校验文件路径格式，提供明确错误提示
2. 后端支持更多路径格式（如 WSL、Cygwin 路径）

**影响文件**：
- `app/modules/library/service.py:138-173`
- `frontend/src/services/api-client.ts:225-242`

**检查清单**：
- [ ] 前端预校验文件路径格式
- [ ] 后端支持 WSL、Cygwin 路径
- [ ] 提供明确错误提示
- [ ] 测试：各种路径格式都能正确处理

---

### P2-2: SSE 缓冲区限制

**来源**: 勾子/5-哪里会断.md

**上下文（证据）**：
- `frontend/src/services/sse-client.ts:287-361` — `readSseStream()` 使用 `buffer` 字符串拼接 SSE 帧
- `frontend/src/services/sse-client.ts:293` — `buffer` 变量在 `while` 循环中不断追加，无大小限制

**问题（断点影响）**：
- 后端高频发送 chunk（每秒 100 次）→ 前端 `buffer` 持续增长，内存占用飙升
- 极端情况下可能导致浏览器标签页崩溃（OOM）

**原因**：
SSE 缓冲区没有大小限制，高频发送会导致内存泄漏。

**决策**：
同意1

**方案**：
设置 `buffer` 最大长度（10MB），超过后丢弃旧数据

**影响文件**：
- `frontend/src/services/sse-client.ts:287-361`

**检查清单**：
- [ ] 设置 `buffer` 最大长度（10MB）
- [ ] 超过上限后丢弃旧数据
- [ ] 测试：高频发送不会导致内存泄漏

---

## P3（延后 - 非紧急）

### P3-1: 前端会话状态持久化

**来源**: 勾子/5-哪里会断.md

**上下文（证据）**：
- `frontend/src/stores/conversation.ts:61-69` — `sessionId` 使用 `crypto.randomUUID()` 生成，刷新页面后丢失
- `frontend/src/stores/conversation.ts:438-449` — `reset()` 后生成新 `sessionId`，但旧会话消息未保存

**问题（断点影响）**：
- 用户刷新页面 → 历史消息丢失，需重新触发问答
- 用户关闭标签页后再打开 → 无法恢复之前的会话

**原因**：
当前 `sessionId` 存储在内存中，刷新页面后丢失。

**决策**：
同意2，这个之后再说

**方案**：
使用 `localStorage` / `sessionStorage` 持久化 `sessionId` 和 `messages`

**影响文件**：
- `frontend/src/stores/conversation.ts:61-69`, `438-449`

**检查清单**：
- [ ] 使用 `localStorage` 持久化 `sessionId` 和 `messages`
- [ ] 或实现后端 `/api/v1/session/{session_id}` 接口
- [ ] 测试：刷新页面后会话恢复

---

### P3-2: 前端错误监控

**来源**: 勾子/5-哪里会断.md

**上下文（证据）**：
- 文件：`frontend/src/main.ts`（未读取完整）
- 风险：生产环境错误无法追踪

**问题（断点影响）**：
生产环境错误无法追踪，难以定位问题

**原因**：
当前没有前端错误监控系统。

**决策**：
这个不着急。先做后端

**方案**：
集成前端错误监控（Sentry / 自建）

**影响文件**：
- `frontend/src/main.ts`

**检查清单**：
- [ ] 集成 Sentry 或自建错误监控
- [ ] 配置错误上报
- [ ] 测试：错误能正确上报

---

### P3-3: 前端 API 地址校验放宽

**来源**: 勾子/5-哪里会断.md

**上下文（证据）**：
- `frontend/src/services/api-client.ts:46-108` — `normalizeConfiguredApiBaseUrl()` 只允许本机回环地址（`127.0.0.1`, `localhost`, `[::1]`）
- `frontend/src/services/api-client.ts:44` — `LOCAL_API_HOSTNAME_ALLOWLIST` 硬编码

**问题（断点影响）**：
- 开发环境下后端部署在 Docker 容器中（IP 如 `172.17.0.2`）→ 前端请求被拒绝，回退到默认 `http://127.0.0.1:8000`
- 用户无法通过环境变量 `VITE_API_BASE_URL` 指向其他本机地址（如 `http://0.0.0.0:8000`）

**原因**：
API 地址白名单过于严格，不适应 Docker 等部署环境。

**决策**：
现在还在开发期，只有我能用

**方案**：
允许 `0.0.0.0` 作为开发环境地址（检测 `import.meta.env.DEV`）

**影响文件**：
- `frontend/src/services/api-client.ts:46-108`, `44`

**检查清单**：
- [ ] 允许 `0.0.0.0` 作为开发环境地址
- [ ] 检测 `import.meta.env.DEV` 判断环境
- [ ] 测试：Docker 容器部署时前端能连接后端

---

## 无需处理

### Qdrant 连接池配置
**来源**: 勾子/5-哪里会断.md
**决策**: 这个待会都重构了，不会高并发的
**说明**: 即将重构，无需处理

---

## 执行顺序

1. **P0-1** → **P0-2** → **P0-3** → **P0-4**（解决阻塞问题）
2. **P1-3** → **P1-4**（修复已知缺陷）
3. **P1-1** → **P1-2**（提升稳定性）
4. **P2-1** → **P2-2**（优化体验）
5. P3 延后处理
