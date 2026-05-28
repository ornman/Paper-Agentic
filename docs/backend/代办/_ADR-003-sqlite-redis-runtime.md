# ADR-003: SQLite + 进程内内存运行态

## Status
Accepted

## Context

SQLite 适合承载长期事实、会话记录和摘要。

而活动窗口、`written_context`、selection、冻结副本这类状态是短期工作态，应该优先留在进程内内存里，避免把本来就会频繁变化的状态强行外置。

默认基线不引入外部缓存服务。

## Decision

- SQLite 保存长期事实
- 进程内内存保存活动窗口、编辑上下文、selection 和冻结副本
- 冻结副本只做短期保留，过期后自动清理
- 进程重启后 live cache 重新建立，不做跨进程恢复
- 如果未来需要外部缓存，必须单独立 ADR，不作为当前基线

## Consequences

优点：

- 部署更简单
- 依赖更少
- 对当前单进程本地助手场景足够

代价：

- 进程重启后 live cache 会丢失
- 需要依赖当前 editor context 和 SQLite 摘要重建工作态
- 不适合拿来做跨进程共享缓存
