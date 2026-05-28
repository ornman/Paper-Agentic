# ADR-001: 后端以三层骨架为活动真相

## Status

Accepted

## Context

前一轮把后端描述成 `Strict Clean / application / domain / infrastructure / interfaces`，但这套语言没有解决当前项目真正的沟通问题：

- 用户关心的是数据怎么准备、Agent 怎么行动、服务怎么稳定暴露
- 旧代码和临时骨架混在一起后，继续强调 Clean 名词只会让目录重排掩盖真实职责
- 当前最需要的是能指导重构顺序的业务骨架，而不是抽象分层口号

## Decision

活动真相源固定为三层：

1. 数据层
2. Agent 层
3. 服务层

后续代码重构、文档拆分、目录 owner、日志与状态机设计，都围绕这三层组织。

`application / domain / infrastructure / interfaces` 这类目录如果继续存在，只能作为迁移中过渡物，不再代表最终活动架构。

## Consequences

正面：

- 文档和业务讨论使用同一套语言
- 能直接指导“先重建数据层，再重建 Agent，再重建服务层”
- 避免把目录翻新误判为完成重构

代价：

- 已经写出来的临时 Clean 骨架不再能直接当目标结构
- 一部分已改代码需要重新归属
