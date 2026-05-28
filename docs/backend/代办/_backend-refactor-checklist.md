# 后端重构清单

这份清单只服务于“三层后端”重构，不再沿用上一版那套以 `application/domain/infrastructure` 为主线的拆法。

## Phase 0: 停线与边界收敛

**输入**

- 最新确认的后端三层目标
- 当前 `backend/app` 混合态代码事实
- “Kimi 不再是活动基线、评测后置”的最新约束

**输出**

- `docs/backend/architecture.md` 写明“先重构后评测”
- `docs/backend/现状代码映射.md` 写明活动链、遗留残留、空壳目录
- `docs/backend/迁移任务表.md` 改成先收敛边界、后接主链
- `backend/.env.example` 不再暗示 Kimi 是活动默认值

**验收**

- 文档里不再出现“后端没重构完就先测”的执行顺序
- 文档里明确写出 `api/clients/core/models/pipelines/stores/utils` 是遗留残留
- 文档里明确写出 `bootstrap/application/domain/infrastructure/interfaces` 是临时骨架，不是最终目录
- 示例配置不再把 Kimi 当默认建议

**遗留删除项**

- 任何把评测排在重构前面的活动表述
- 任何把 Kimi 套餐写成当前默认主链的活动表述

## Phase A: 先把架构文档定明白

**输入**

- 你现在对后端的明确要求
- `archives/_arch_doc` 中还能用的历史判断
- 当前 `backend/` 代码现状

**输出**

- `docs/backend/architecture.md`
- `docs/backend/现状代码映射.md`
- `docs/backend/迁移任务表.md`
- `docs/backend/实施切片.md`
- `docs/backend/代办/后端架构待办.md`
- 本清单

**验收**

- 文档能独立讲清楚三层职责
- 文档明确写出 `PDF + DOCX`
- 文档明确写出 Agent 的会话、缓存、按需检索、摘要 hook、tool call、loop、tasklist
- 文档明确写出 WPS 轮询和编辑器上下文
- 文档明确写出日志/观测是正式能力
- 文档明确写出实施切片和首批落代码顺序

**遗留删除项**

- 旧的、不可读的活动架构表达

## Phase B: 重建数据层

**输入**

- Docling 官方能力与现有 PDF 解析、清洗、图片处理、索引代码
- Anthropic PDF / DOCX skills 的可借鉴处理方式
- 文档中锁定的数据层职责

**输出**

- Docling 接入
- 本地文件导入入口
- PDF / DOCX 统一预处理
- Markdown + JSON 元数据产物
- 图片语义增强
- parent-child chunk
- chunk 与原文锚点
- 向量索引 + 关键词索引
- tokenizer 长度校验与批量 padding/truncation 规则

**验收**

- 同一套数据层通过 Docling 处理 PDF 和 DOCX
- 每个 chunk 都能反查回原文段落或页码锚点
- 图片语义子块能随父块联动
- retrieval chunk 与 answer context pack 已分离
- 超长输入不会静默越过模型上限
- 单文档导入、删除、重建都能独立完成
- 数据层只负责知识准备和检索，不直接承载对话逻辑

**遗留删除项**

- 把“解析 + 问答 + HTTP”揉在一起的实现

## Phase C: 重建 Agent 层

**输入**

- 数据层检索能力
- 会话持久化和缓存能力

**输出**

- 会话管理
- 活动窗口缓存
- `written_context` 常驻监听
- 检索决策
- reflection
- 回答生成
- 原文引用与回跳信息
- 摘要压缩 hook
- 上下文 token 监控
- tool call / loop / tasklist 基础运行时
- 请求级阶段日志与可观测状态

**验收**

- Agent 能区分 `written_context / selection / prompt`
- Agent 能按四种场景使用固定权重起手
- 对话请求消费的是冻结副本，不污染持续监听流
- Agent 能决定“要不要检索”
- Agent 能分批取证并在轮间做 reflection
- 回答结果带直接依据和原文定位信息
- 可用上下文低于 `5%` 时触发 compact
- 状态机支持 retry / degrade / needs_user_action
- 对话级关键阶段有结构化日志
- 进程内运行态初始化失败时能回退到空窗口，而不是整条链路崩掉

**遗留删除项**

- 只会“固定检索 -> 固定回答”的伪 Agent 逻辑
- 靠全局内存拼状态的实现

## Phase D: 重建服务层

**输入**

- 数据层和 Agent 层已成形

**输出**

- API
- SSE
- 配置
- 启动与健康检查
- WPS editor context 同步接口
- 上下文 token 统计可见性
- 进程内活动窗口可见性与清理信号
- 日志与观测出口

**验收**

- 服务层不再写业务推理
- API 只做协议适配和错误映射
- 健康检查能反映 degraded 状态
- editor context 作为独立入口存在，不混进普通聊天接口
- SSE 或等效接口能让前端显示当前上下文窗口 token 使用情况
- 活动窗口接近上下文预算上限时能触发 compact，并在必要时停止继续膨胀
- 导入、对话、compact、retry/degrade 事件都能被观察到

**遗留删除项**

- 旧路由命名
- 旧轮询命名
- 旧上传式导入接口

## Phase E: 迁移旧代码并清理目录

**输入**

- 三层实现已经跑通

**输出**

- 旧代码复用完毕或废弃完毕
- 目录树和职责彻底对齐三层结构

**验收**

- 后端目录以 `data_layer / agent_layer / service_layer` 为主
- 旧 `services / stores / clients / pipelines` 不再主导活动实现
- 我前面临时搭出来的 `application / domain / infrastructure / interfaces` 也不再主导活动实现

**遗留删除项**

- 与目标三层无关的中间过渡目录

## Phase F: 后置接入评测体系

**输入**

- 数据层、Agent 层、服务层主链已经稳定
- 旧目录已经冻结，不再承载新功能

**输出**

- 黑盒 runner
- 内部态 runner
- A/B runner
- judge 与报告系统

**验收**

- 评测对象是三层主链，不是混合态旧实现
- 评测基线不再依赖 Kimi 套餐
- 黑盒、内部态、A/B 的差异边界清楚

**遗留删除项**

- 在混合态实现上做的临时评测脚本或结论
