# ADR-002: PDF/DOCX 采用路由式文档处理链

## Status

Accepted

## Context

旧实现把 MinerU 作为 PDF 主解析链，而且基本只围绕 PDF 思考。现在目标已经改变：

- 第一版必须同级支持 `PDF + DOCX`
- 总架构不能继续把单一解析器写死为默认主链
- 当前默认方案必须能在普通 Windows 机器稳定运行
- 后端需要统一面对 `Markdown + JSON 元数据`，而不是为 PDF 和 DOCX 分别维护两套完全不同的数据模型

同时，用户已经明确给出两个参考来源：

- `markitdown`
- `docling-project/docling`
- `marker`
- `anthropics/skills/pdf`、`anthropics/skills/docx`

## Decision

- 文档预处理采用“探针路由 + 多策略处理链”，不默认绑定单一解析器
- `PDF` 当前默认方向是轻量优先：
  - 轻量探针
  - 轻量文本主链
  - 按需走图片 / OCR / 表格 / 公式增强 API
- `Marker`、`Docling` 只作为可选增强能力，不是当前普通机器的默认本地主链
- 主产物固定为：
  - `markdown`
  - `structured json`
  - `extraction report`
  - 锚点与必要原始证据
- 具体实现细节下沉到模块文档维护，而不是继续堆在总架构文档里

## Consequences

正面：

- PDF 和 DOCX 可以进入统一数据层
- 主链不再绑死单一 PDF 解析器
- 后续 chunk、anchor、indexing 都有统一输入格式
- 架构文档和模块文档分层更清楚
- 可以按机器能力和文档特征灵活分流

代价：

- 旧 MinerU / Docling 主基线表述需要同步退场
- 需要补齐模块级文档和路由阈值
- 远程增强链的成本与降级策略需要额外设计
