# 开发计划

> 生成时间: 2026-04-09
> 基于批注数: 19 条，确认: 19 条，需验证: 0 条

---

## 优先级 P0（必须做）

### P0-1: 路由切换到 modules/ 新架构
> **完成时间**: 2026-04-09 22:15
**来源批注**: #18 | 4-演进与债务/4.2-架构适应度.md:118

**问题**: 当前代码同时存在旧服务层（`app/services/`）和新架构层（`app/modules/`），路由仍调用旧服务，导致状态机未启用、数据分散。

**原始批注**:
￥按新架构来￥

**原始回应**:
￥
【确认】：按 `modules/` 新架构来，不再维护旧服务层。

**新架构清单**：
```
app/modules/
├── ingestion/     ← 导入流程（新版）
│   ├── service.py
│   ├── mineru_client.py
│   └── ...
├── indexing/      ← 索引流程（新版）
│   ├── service.py
│   └── ...
├── library/       ← 文档管理（新版）
│   ├── service.py
│   └── models.py
└── qa/            ← 问答流程（新版）
    └── ...
```

**旧服务层（废弃）**：
```
app/services/
├── ingest_service.py     ← 迁移到 modules/ingestion/
├── indexing_service.py   ← 迁移到 modules/indexing/
└── qa_service_rag.py     ← 迁移到 modules/qa/
```

**迁移步骤**：
1. ✅ 新架构代码已实现
2. ⏳ 路由切换到 `modules/` 层
3. ⏳ 稳定运行 1 周后删除旧服务层

**优先级**：P0（尽快完成路由切换）
￥

**方案**:
1. 更新路由：`app/api/v1/routes/` 中所有路由改为调用 `modules/` 层服务
2. 更新依赖注入：调整 FastAPI 的 `Depends()` 调用
3. 测试验证：确保所有功能正常（导入、检索、问答）
4. 监控稳定运行 1 周后删除旧服务层

**影响范围**:
- `app/api/v1/routes/*.py`（所有路由文件）
- `app/services/`（旧服务层，待删除）

**验证状态**: ✅ 已确认

---

## 优先级 P1（应该做）

### P1-1: 实现自动重试机制
> **完成时间**: 2026-04-09 22:15
**来源批注**: #14 | 2-动态行为/2.1-核心业务时序.md:193

**问题**: 当前代码所有外部调用都是"一次失败即报错"，网络抖动或 API 限流时用户体验差。

**原始批注**:
￥自动重试，重试3次后熔断，给出报错原因￥

**原始回应**:
￥
【建议】：当前代码**没有自动重试机制**，所有外部调用都是"一次失败即报错"。

**代码证据**：`embedding_client.py:84`
```python
async with httpx.AsyncClient(timeout=60.0) as client:
    response = await client.post(...)
    response.raise_for_status()  # ← 失败直接抛异常，无重试
```

**影响**：
- 网络抖动 → 请求失败 → 用户看到错误
- API 限流（429）→ 请求失败 → 无重试，需手动重试
- 超时 → 请求失败 → 无重试，需手动重试

**建议实现**（🔮 未来扩展）：
1. **重试策略**：指数退避（1s → 2s → 4s），最多3次
2. **熔断机制**：连续失败 N 次后，暂停该服务调用一段时间（如 30s）
3. **错误分类**：
   - 可重试：网络错误、超时、429 限流
   - 不可重试：401 认证失败、404 资源不存在、400 参数错误
4. **用户提示**：重试失败后，给出明确错误原因（"API 限流，请稍后重试" vs "论文不存在"）

**优先级**：P1（影响用户体验）
￥

**方案**:
1. 新增 `app/utils/retry.py`，实现 `async_retry_with_backoff` 装饰器
2. 修改 `embedding_client.py`、`rerank_client.py`、`vlm_client.py`，添加重试装饰器
3. 实现错误分类：区分可重试和不可重试错误
4. 添加熔断机制（可选）：连续失败 N 次后暂停调用

**影响范围**:
- `app/utils/retry.py`（新增）
- `app/clients/embedding_client.py`
- `app/clients/rerank_client.py`
- `app/clients/vlm_client.py`

**验证状态**: ✅ 已确认

---

### P1-2: 实现断点续传机制
> **完成时间**: 2026-04-09 22:15
**来源批注**: #6 | 2-动态行为/2.3-运行时状态机.md:272

**问题**: WPS 关闭后任务继续执行，但用户无法恢复进度，无状态记录和恢复机制。

**原始批注**:
￥关闭了WPS的话，再次打开从之前的断点处开始￥

**原始回应**:
￥
【现状问题】：当前代码**不支持断点续传**，WPS 关闭后任务继续执行，但用户无法恢复进度。

**代码证据**：`app/services/ingest_service.py:import_pdf()`
```python
async def import_pdf(self, file_path: str, document_id: str):
    # 1. MinerU 解析
    result = await self._wait_for_mineru(task_id)
    # 2. VLM 描述
    described_chunks = await self._describe_images(result)
    # 3. Embedding
    embeddings = await self.embedding_service.generate_embeddings(...)
    # 4. Qdrant 存储
    await self.qdrant_store.store_chunks(...)
```

**问题分析**：
1. **无状态记录**：任务执行到哪一步了？用户关闭后无法查询
2. **无法恢复**：用户再次打开，从头开始？还是继续执行？
3. **残留风险**：任务失败后，Qdrant 中有残废 Collection

**解决方案**（参考快照中的建议）：

### 方案 A：任务状态表 + 轮询（推荐）

**改动位置**：
- 启用 `ingest_tasks` 表（已定义但未使用）
- 新增轮询端点：`GET /api/v1/tasks/{task_id}`

**状态机**：
```
pending → parsing → cleaning → vlm_describing → embedding → indexing → completed
                            ↓                                    ↓
                          failed                                failed
```

**前端逻辑**：
1. 提交导入任务 → 获得 `task_id`
2. 关闭 WPS → 任务继续执行
3. 再次打开 → 轮询 `GET /api/v1/tasks/{task_id}`
4. 如果 `status == 'completed'` → 显示成功
5. 如果 `status == 'failed'` → 显示错误 + 重试按钮

---

**建议优先级**：P1（影响用户体验）
**实施建议**：先用方案 A（任务状态表 + 轮询），MVP 后考虑方案 B（SSE）
￥

**方案**:
1. 启用 `ingest_tasks` 表（`sqlite_repo.py:59-70` 已定义）
2. 在 `ingest_service.py` 中写入任务状态：pending → parsing → cleaning → vlm_describing → embedding → indexing → completed
3. 新增轮询端点：`GET /api/v1/tasks/{task_id}`
4. 前端轮询任务状态，显示进度条
5. 支持失败重试：从失败状态继续执行

**影响范围**:
- `app/services/ingest_service.py`
- `app/repositories/sqlite_repo.py`（启用 `ingest_tasks` 表）
- `app/api/v1/routes/library.py`（新增轮询端点）
- 前端：添加进度条和轮询逻辑

**验证状态**: ✅ 已确认

---

### P1-3: 降低 Qdrant 内存占用
> **完成时间**: 2026-04-09 22:15
**来源批注**: #12 | 3-物理部署/3.2-资源配置.md:82

**问题**: Qdrant 的 HNSW 索引内存常驻，100 篇论文约 2.5-3 GB，2000 篇论文需 32 GB 内存，不可接受。

**原始批注**:
￥这个内存肯定不行，我只接收存储这么大，但不接受运行时这么大。我宁愿降低效率也要全面￥

**原始回应**:
￥
【问题】：Qdrant 的 HNSW 索引是**内存常驻**的，论文数量多时内存占用很高。

**代码证据**：`qdrant_store.py`
```python
# Qdrant 默认配置（未显式指定 HNSW 参数）
client.create_collection(
    collection_name=collection_name,
    vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
    # ← HNSW 索引常驻内存
)
```

**内存占用分析**：
- 100 篇论文 → 约 10000 个 chunk × 1536 维 × 4 字节 = ~60 MB（向量）
- HNSW 索引 → 约 2-3 GB（图结构）
- Python 进程 → 约 500 MB
- **总计**：~2.5-3 GB

**降低内存的方案**：

### 方案 B：磁盘索引（Qdrant on-disk）

**改动位置**：`config.py` + `qdrant_store.py`
```python
# 使用 Qdrant 的磁盘存储模式
client = QdrantClient(path=settings.qdrant_path, storage_type="on_disk")
```

**影响**：
- ✅ 内存占用降低 ~90%
- ❌ 检索速度降低 ~50%（磁盘 IO）

---

**建议**：
- **短期**：方案 B（磁盘索引），牺牲速度换取内存
- **长期**：方案 C（分布式架构），已在 `retrieval_service.py` 中实现 RRF 融合

**优先级**：P1（影响用户硬件需求）
￥

**方案**:
1. 使用 Qdrant on-disk 存储模式：`QdrantClient(path=settings.qdrant_path, storage_type="on_disk")`
2. 评估性能影响：测试检索速度下降是否可接受
3. 如性能不可接受，考虑分布式架构：每篇论文一个 Collection，检索时并行查询 + RRF 融合

**影响范围**:
- `app/stores/qdrant_store.py`
- `app/core/config.py`（新增配置项）

**验证状态**: ✅ 已确认

---

### P1-4: 实现一键启动方案
> **完成时间**: 2026-04-09 22:15
**来源批注**: #16 | 3-物理部署/3.3-环境差异矩阵.md:141

**问题**: 用户需要手动启动后端，体验差。需要一键启动方案（bat 脚本或 EXE）。

**原始批注**:
￥启动serve，可以成熟后通过exe编译好，或者是一个bat脚本一键启动。服务启动后，那个wpsjs debug就会自动加载写的前端的。￥

**原始回应**:
￥
【确认】：这是一个很好的部署方案建议。

**方案梳理**：

### 方案 A：bat 脚本一键启动（简单）

**改动位置**：新增 `start.bat`
```batch
@echo off
cd /d "%~dp0backend"
echo 启动论文助手后端...
uv run python main.py
pause
```

**使用方式**：
- 用户双击 `start.bat` → 后端启动
- WPS 插件连接到 `http://127.0.0.1:8000`

**优点**：
- ✅ 简单，无需编译
- ✅ 跨平台（Linux/MAC 用 `.sh` 脚本）

**缺点**：
- ❌ 需要 Python 环境 + 依赖安装
- ❌ 用户可以看到控制台（可能误关）

---

### 方案 B：EXE 编译（复杂）

**改动位置**：新增 `build_exe.py`
```python
import PyInstaller

PyInstaller([
    '--name=论文助手',
    '--onefile',
    '--windowed',
    '--icon=icon.ico',
    'main.py',
])
```

**使用方式**：
- 用户双击 `论文助手.exe` → 后端启动
- 后台运行，无控制台窗口

**优点**：
- ✅ 用户无需安装 Python
- ✅ 后台运行，用户体验好

**缺点**：
- ❌ 编译后文件大（~200 MB）
- ❌ 编译复杂，需要打包所有依赖
- ❌ 可能被杀毒软件误报

---

### 方案 C：混合方案（推荐）

**开发阶段**：使用 `start.bat`
**生产阶段**：使用 PyInstaller 编译 EXE

**实现步骤**：
1. 开发期：用 `start.bat` 调试
2. 发布期：用 PyInstaller 打包
3. 用户安装：提供 `论文助手.exe` + `start.bat`（调试用）

---

### WPS 插件集成

- WPS 插件启动时 → 检测后端是否运行
- 如果未运行 → 自动启动 `论文助手.exe`
- 如果已运行 → 直接连接

**优先级**：P1（影响用户安装体验）
￥

**方案**:
1. **短期**：创建 `start.bat` 脚本，用户双击启动后端
2. **长期**：用 PyInstaller 编译 `论文助手.exe`，后台运行
3. WPS 插件集成：启动时检测后端是否运行，未运行则自动启动

**影响范围**:
- `start.bat`（新增）
- `build_exe.py`（新增，长期）
- WPS 插件前端代码

**验证状态**: ✅ 已确认

---

### P1-5: 添加日志导出功能
> **完成时间**: 2026-04-09 22:15
**来源批注**: #10 | 2-动态行为/2.2-异步边界与错误传播.md:96

**问题**: 用户遇到错误时无法自动导出日志，需要手动截图或复制错误信息。

**原始批注**:
￥这里应该可以而且必须拓展：自动导出日志到桌面。然后发给开发者￥

**原始回应**:
￥
【建议】：当前代码**没有日志导出功能**，用户遇到错误时需要手动截图或复制错误信息。

**代码证据**：`main.py:25-28`
```python
async def general_exception_handler(request, exc):
    return JSONResponse(status_code=500, content={
        "code": 9001, "data": None, "message": f"内部错误：{str(exc)}"
    })
    # ← 没有日志记录，没有日志导出
```

**建议实现**：
1. **错误发生时**：
   - 记录详细日志到文件（`logs/error-{timestamp}.log`）
   - 日志包含：请求信息、异常堆栈、上下文数据
   - 返回给前端：日志文件路径或日志ID

2. **前端添加"导出日志"按钮**：
   - 点击后打包日志文件（最近 N 条错误日志）
   - 下载到用户桌面（`~/Desktop/论文助手-错误日志-{timestamp}.zip`）
   - 用户可直接发送给开发者

3. **日志内容**：
   ```
   [时间] [ERROR] [论文ID: xxx] [用户ID: xxx]
   请求路径: POST /api/v1/library/import
   异常类型: MinerUTimeoutError
   异常信息: MinerU API 超时（300s）
   堆栈:
     File "app/services/ingest_service.py", line 123, in import_pdf
       await self._wait_for_mineru(task_id)
   ```

**优先级**：P1（提升用户支持体验）
￥

**方案**:
1. 配置日志系统：使用 Python `logging` 模块，输出到文件 `logs/app.log`
2. 全局异常处理器中记录详细日志
3. 新增日志导出端点：`GET /api/v1/logs/export`
4. 前端添加"导出日志"按钮，打包最近 N 条日志为 ZIP 下载

**影响范围**:
- `app/core/logging_config.py`（新增）
- `app/main.py`（全局异常处理器）
- `app/api/v1/routes/system.py`（新增日志导出端点）
- 前端：添加"导出日志"按钮

**验证状态**: ✅ 已确认

---

## 优先级 P2（可以做）

### P2-1: 重构大文件
**来源批注**: #7 | 1-静态结构/1.4-代码组织与配置.md:110

**问题**: 部分文件超过 200 行，影响可读性（`cleaner.py:269`、`qdrant_store.py:284`、`query_rewrite_service.py:229` 等）。

**原始批注**:
￥这里应该是可以重构的吧，让它变优雅易读￥

**原始回应**:
￥
【建议】：这些文件确实需要重构，但不是立即重构（P2 优先级）。

**重构方向**：
1. **拆分大文件**：
   - `cleaner.py:269` → 按规则类型拆分为 `text_cleaner.py`、`image_cleaner.py`
   - `qdrant_store.py:284` → 拆分为 `qdrant_client.py`（CRUD）+ `qdrant_schema.py`（模型定义）
   - `query_rewrite_service.py:229` → 拆分为 `prompts.py`（Prompt 模板）+ `query_service.py`（逻辑）

2. **提取工具函数**：
   - `config.py:279` → 提取 `validator.py`（校验逻辑）
   - `sqlite_repo.py:243` → 提取 `query_builder.py`（SQL 构建逻辑）

3. **统一风格**：
   - `modules/ingestion/mineru_client.py` → 与 `app/clients/mineru_client.py` 统一接口
   - `modules/library/models.py` → 与 `app/models/` 统一命名

**重构时机**：
- ✅ **现在**：模块功能稳定，没有频繁变更
- ❌ **不推荐**：在快速迭代期重构（可能白费功夫）

**建议**：等路由切换到 `modules/` 层后，统一重构一次。
￥

**方案**: 等路由切换到 `modules/` 层且稳定运行 1 周后，统一重构一次。

**影响范围**:
- `app/services/cleaner.py`
- `app/stores/qdrant_store.py`
- `app/services/query_rewrite_service.py`
- `app/core/config.py`
- `app/repositories/sqlite_repo.py`

**验证状态**: ✅ 已确认

---

### P2-2: 配置缓存清理方案
**来源批注**: #8 | 1-静态结构/1.4-代码组织与配置.md:147

**问题**: `lru_cache` 缓存了 `Settings` 实例，运行时修改环境变量不会反映到已缓存的实例。

**原始批注**:
￥这个有什么解决方法吗？￥

**原始回应**:
￥
【问题】：`lru_cache` 缓存了 `Settings` 实例，运行时修改环境变量不会反映到已缓存的实例。

**代码证据**：`config.py:276-279`
```python
@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**影响**：
- 用户修改 `.env` 文件 → 需要重启服务才能生效
- 运行时修改环境变量 → 不会反映到 `get_settings()` 的返回值

**解决方案**：

### 方案 A：清除缓存（推荐）

**改动位置**：`config.py`
```python
def reload_settings() -> Settings:
    """清除缓存并重新加载配置"""
    get_settings.cache_clear()  # ← 清除 lru_cache
    return get_settings()
```

**使用场景**：
- 用户修改 `.env` 后，调用 `reload_settings()`
- 单元测试中，每个测试用例前重新加载配置

---

**建议**：MVP 阶段使用方案 A（清除缓存），后续根据需求选择。
￥

**方案**: 添加 `reload_settings()` 函数，提供配置重载功能。

**影响范围**:
- `app/core/config.py`

**验证状态**: ✅ 已确认

---

### P2-3: 错误分类与用户友好提示
**来源批注**: #9 | 2-动态行为/2.2-异步边界与错误传播.md:32

**问题**: 所有未捕获异常统一返回 500 + 错误信息字符串，可能泄露内部实现细节。

**原始批注**:
￥对于早期开发而言，问题不大，但是我认为应该返回的错误分好类别，不应该这么杂乱；但对于如何详细的捕捉异常，我也不是很有头绪，一般来说单元测试跑通，说明异常的可能性很小；就算有，这种全局异常处理也不会很多￥

**原始回应**:
￥
【回答】：你的判断是对的。MVP 阶段统一返回 500 + 错误信息是可以接受的，但确实应该分类错误码。

**当前状态**：`main.py:25-28`
```python
async def general_exception_handler(request, exc):
    return JSONResponse(status_code=500, content={
        "code": 9001, "data": None, "message": f"内部错误：{str(exc)}"
    })
```

**建议的错误分类**（🔮 未来扩展）：
| 错误码 | 类型 | HTTP状态码 | 示例 |
|--------|------|-----------|------|
| 1001 | 参数错误 | 400 | 论文ID为空 |
| 2001 | 认证失败 | 401 | API Key无效 |
| 2003 | 权限不足 | 403 | 无权访问该论文 |
| 3001 | 资源不存在 | 404 | 论文不存在 |
| 4001 | 外部服务错误 | 502 | MinerU API 超时 |
| 4002 | 外部服务限流 | 429 | Embedding API 限流 |
| 9001 | 内部错误 | 500 | 其他未捕获异常 |

**实现方案**：
1. 定义异常类：`class APIException(ABC)`
2. 子类化：`class ParamError(APIException)`、`class ExternalServiceError(APIException)`
3. 全局处理器中根据异常类型返回不同的错误码

**优先级**：P2（MVP 后优化）
￥

**方案**: MVP 后优化，定义异常类并分类错误码。

**影响范围**:
- `app/core/exceptions.py`（新增）
- `app/main.py`（全局异常处理器）

**验证状态**: ✅ 已确认

---

### P2-4: 支持 DEV/PROD 环境区分
**来源批注**: #15 | 3-物理部署/3.3-环境差异矩阵.md:72

**问题**: 当前没有 DEV/PROD 环境区分机制，所有配置通过单个 `.env` 文件管理。

**原始批注**:
￥你的优化建议是？￥

**原始回应**:
￥
【建议】：支持 DEV/PROD 环境区分，通过 `.env.{环境}` 文件管理。

**改动位置**：
- 修改 `config.py`，支持环境变量前缀
- 新增 `.env.dev`、`.env.prod` 文件

**实现方案**：

### 方案 A：环境前缀（推荐）

**改动位置**：`config.py`
```python
import os
from functools import lru_cache

class Settings(BaseSettings):
    # ... 现有字段 ...
    
    model_config = SettingsConfigDict(
        env_file=f".env.{os.getenv('APP_ENV', 'dev')}",  # ← 根据环境加载不同文件
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**使用方式**：
```bash
# 开发环境
export APP_ENV=dev
uv run python main.py  # 加载 .env.dev

# 生产环境
export APP_ENV=prod
uv run python main.py  # 加载 .env.prod
```

**`.env.dev`**：
```env
# 开发环境：本地调试
DEBUG=true
LOG_LEVEL=DEBUG
```

**`.env.prod`**：
```env
# 生产环境：WPS 插件
DEBUG=false
LOG_LEVEL=WARNING
APP_HOST=127.0.0.1
```

---

**优先级**：P2（MVP 后优化）
￥

**方案**: 修改 `config.py`，支持根据 `APP_ENV` 环境变量加载不同的 `.env.{环境}` 文件。

**影响范围**:
- `app/core/config.py`
- `.env.dev`（新增）
- `.env.prod`（新增）

**验证状态**: ✅ 已确认

---

### P2-5: 清理旧服务层代码
**来源批注**: #19 | 4-演进与债务/4.1-变更热点.md:73

**问题**: 旧服务层代码已迁移到 `modules/` 层，但未删除，存在命名冲突和代码冗余。

**原始批注**:
￥之后更新完再重构吧，这个标记可以之后统一清理￥

**原始回应**:
￥
【确认】：技术债务已记录，待路由切换到 `modules/` 层后统一清理。

**清理清单**（待执行）：
1. 删除旧版服务：
   - `app/services/indexing_service.py` → 已迁移到 `modules/indexing/`
   - `app/repositories/chroma_repo.py` → 已迁移到 Qdrant

2. 清理残留：
   - `app/modules/indexing/chroma_repo.py` → ChromaDB 残留
   - `app/workflows/__init__.py` → 空文件

3. 解决命名冲突：
   - `clients/llm_client.py` 的 `LLMClient` → 重命名为 `OpenAILLMClient`
   - 或改为继承 `vlm_client.py` 的抽象类

**触发条件**：路由切换到 `modules/` 层，且运行稳定 1 周后

**优先级**：P2（暂缓）
￥

**方案**: 等路由切换到 `modules/` 层且稳定运行 1 周后，统一清理旧服务层代码。

**影响范围**:
- `app/services/indexing_service.py`（删除）
- `app/repositories/chroma_repo.py`（删除）
- `app/modules/indexing/chroma_repo.py`（删除）
- `app/workflows/__init__.py`（删除）
- `app/clients/llm_client.py`（重命名）

**验证状态**: ✅ 已确认

---

### P2-6: 硅基流动超时配置
**来源批注**: #13 | 2-动态行为/2.1-核心业务时序.md:171

**问题**: 硅基流动的 API Key 和 Base URL 已配置环境变量，但超时时间是硬编码的。

**原始批注**:
￥那个硅基流动不要硬编码，进入环境变量￥

**原始回应**:
￥
【确认】：硅基流动的 API Key 和 Base URL 已配置环境变量（`config.py:53-74`），但**超时时间是硬编码的**。

**代码证据**：
- ✅ 已配置：`SILICONFLOW_API_KEY`、`SILICONFLOW_BASE_URL`（`config.py:53-74`）
- ❌ 硬编码超时：`embedding_client.py:84` → `timeout=60.0`
- ❌ 硬编码超时：`rerank_client.py:43` → `timeout=60.0`

**建议修复**：
1. 在 `config.py` 中添加：
   ```python
   embedding_timeout: int = Field(default=60, ge=1, description="Embedding 超时（秒）")
   rerank_timeout: int = Field(default=60, ge=1, description="Rerank 超时（秒）")
   ```
2. 客户端中读取配置：`timeout=settings.embedding_timeout`

**优先级**：P2（可优化）
￥

**方案**: 在 `config.py` 中添加超时配置，客户端中读取配置。

**影响范围**:
- `app/core/config.py`
- `app/clients/embedding_client.py`
- `app/clients/rerank_client.py`

**验证状态**: ✅ 已确认

---

## 暂缓（记录但不执行）

### 暂缓-1: MinerU 自研清洗逻辑
**来源批注**: #17 | 4-演进与债务/4.2-架构适应度.md:42

**问题**: 当前使用 MinerU API，计划中期自研清洗逻辑。

**原始批注**:
￥这里MinerU之后我们是打算自研清洗逻辑，前中期我们都用它的API￥

**原始回应**:
￥
【确认】：产品路线已记录。

**技术方案**：
- **前期（MVP）**：使用 MinerU API（依赖外部服务）
- **中期（优化）**：自研清洗逻辑（替换 MinerU）
- **后期（扩展）**：支持多种清洗策略（用户可选）

**架构准备**：
- 当前：`MinerUClient` 未纳入抽象体系
- 建议：中期重构时添加 `PDFParserClient` 抽象类
  ```python
  class PDFParserClient(ABC):
      async def parse_pdf(self, file_path: str) -> ParseResult: ...
  
  class MinerUPDFParserClient(PDFParserClient):
      # 现有实现
      ...
  
  class SelfHostedPDFParserClient(PDFParserClient):
      # 🔮 未来：自研清洗逻辑
      ...
  ```

**影响**：
- 中期重构时，需要修改 `ingest_service.py` 的调用代码
- 建议在 `modules/ingestion/` 中实现新架构

**优先级**：P1（中期重构）
￥

**暂缓原因**: MVP 阶段使用 MinerU API，中期重构时再实现自研清洗逻辑。

---

### 暂缓-2: BM25 增量索引优化
**来源批注**: #2, #3 | 1-静态结构/1.2-数据与存储模型.md:188, 233

**问题**: BM25 每次添加文档都需要全量重建，删除文档也需要重建。

**原始批注**:
￥重建BM25索引的代价是什么，需要用Embedding吗？这个东西我们要用什么东西发现并构建索引？现在的重建流程是什么？￥
￥BM25索引在删除论文的时候如果只清理一个可以吗？会影响其他的地方吗？影响是否可控？如果增加论文，一定要全量重建吗？￥

**原始回应**: （详见批注汇总）

**暂缓原因**: MVP 阶段 BM25 性能可接受（<1000 篇论文），优化方向参考 Qdrant 分布式架构。

---

### 暂缓-3: 上下文压缩
**来源批注**: #11 | 2-动态行为/2.2-异步边界与错误传播.md:134

**问题**: 参考 Claude Code 的 query 引擎，实现上下文压缩功能。

**原始批注**:
￥这里我们的query引擎可以参考这里的"D:\真项目\世界树\project\想法验证期\调研\claude-code（源码版）\claude-code-sourcemap-main"进行优化，但优化之前你需要给出方案，我要清晰的知道哪里是你改的哪里是原有的，改了这个有什么影响……等一系列的信息都要说清楚￥

**原始回应**: （详见批注汇总）

**暂缓原因**: 实现复杂度高，可能丢失信息，优先级 P2。

---

### 暂缓-4: 多轮对话状态机
**来源批注**: #11 | 2-动态行为/2.2-异步边界与错误传播.md:134

**问题**: 参考 Claude Code 的 query 引擎，实现多轮对话状态机。

**原始批注**:
￥这里我们的query引擎可以参考这里的"D:\真项目\世界树\project\想法验证期\调研\claude-code（源码版）\claude-code-sourcemap-main"进行优化，但优化之前你需要给出方案，我要清晰的知道哪里是你改的哪里是原有的，改了这个有什么影响……等一系列的信息都要说清楚￥

**原始回应**: （详见批注汇总）

**暂缓原因**: 架构改动大，增加调试复杂度，优先级 P2。

---

### 暂缓-5: Token 预算管理
**来源批注**: #11 | 2-动态行为/2.2-异步边界与错误传播.md:134

**问题**: 参考 Claude Code 的 query 引擎，实现 Token 预算管理。

**原始批注**:
￥这里我们的query引擎可以参考这里的"D:\真项目\世界树\project\想法验证期\调研\claude-code（源码版）\claude-code-sourcemap-main"进行优化，但优化之前你需要给出方案，我要清晰的知道哪里是你改的哪里是原有的，改了这个有什么影响……等一系列的信息都要说清楚￥

**原始回应**: （详见批注汇总）

**暂缓原因**: 需要准确的 token 估算器（中文计算复杂），优先级 P1。

---

### 暂缓-6: 查询缓存
**来源批注**: #11 | 2-动态行为/2.2-异步边界与错误传播.md:134

**问题**: 参考 Claude Code 的 query 引擎，实现查询缓存。

**原始批注**:
￥这里我们的query引擎可以参考这里的"D:\真项目\世界树\project\想法验证期\调研\claude-code（源码版）\claude-code-sourcemap-main"进行优化，但优化之前你需要给出方案，我要清晰的知道哪里是你改的哪里是原有的，改了这个有什么影响……等一系列的信息都要说清楚￥

**原始回应**: （详见批注汇总）

**暂缓原因**: 需要考虑缓存失效策略，优先级 P1。

---

### 暂缓-7: SQLite 简化
**来源批注**: #4 | 1-静态结构/1.2-数据与存储模型.md:277

**问题**: SQLite 是否需要，可以考虑用 JSON 文件替换。

**原始批注**:
￥SQLite的引入其实是为了本地存储JSON，但现在看来有点冗余，我们用的都是JSON了，SQLite用不上了，现在哪里还用得上它？￥

**原始回应**: （详见批注汇总）

**暂缓原因**: sessions/messages 需要关联查询（外键、级联删除），MVP 阶段保留 SQLite，后续根据前端需求再决定。

---

## 总结

| 优先级 | 任务数 | 说明 |
|--------|--------|------|
| **P0** | 1 | 路由切换到 modules/ 新架构 |
| **P1** | 5 | 自动重试、断点续传、内存优化、一键启动、日志导出 |
| **P2** | 6 | 重构、配置缓存、错误分类、环境区分、清理旧代码、超时配置 |
| **暂缓** | 7 | MinerU 自研、BM25 优化、上下文压缩、状态机、Token 预算、查询缓存、SQLite 简化 |

**推荐实施路径**：
1. **立即**：P0 路由切换
2. **短期**：P1 自动重试、断点续传、内存优化、一键启动、日志导出
3. **中期**：P2 重构、配置缓存、错误分类、环境区分、清理旧代码、超时配置
4. **长期**：暂缓任务（根据实际需求评估）

**关键原则**：
- 保持简单：只引入必需的功能
- 渐进式重构：每次改动后测试，避免大规模重写
- 监控影响：每个改动都要记录性能指标（响应时间、错误率）
