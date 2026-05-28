# VLM 请求编排与降级策略

## 1. 这份文档讨论什么

这份文档只讨论运行侧问题：

- 什么时候自动回调 `VLM`
- 请求如何编排
- 并发和重试怎么定
- 失败后如何降级

这里不讨论：

- 本地部署大模型
- `OCR` 的具体接法
- 代码实现细节

---

## 2. 当前版本边界

这一轮的默认链路明确为：

- 解析器先产出 `markdown + anchors + visual_blocks`
- 只要出现图片类视觉块，就自动触发 `VLM` 增强
- 当前先做 `VLM-first`
- `OCR` 暂不作为默认链路启用，只在文档设计上预留插槽

因此本文件里提到的表单、公式、表格，本轮都先按“视觉块 + VLM 描述”处理。

---

## 3. 供应商与运行假设

当前约束已经锁定：

- OpenAI 兼容接口：`https://api.coro0.top/v1`
- 模型：`qwen3-vl:235b`
- 密钥来源：用户级环境变量 `My_ProxyAPI_KEY`
- 最佳并发：`5`
- 允许异步执行
- 自动重试：`3` 次
- 退避策略：带抖动的指数退避

当前不再额外设计本地备用模型。

如果这个镜像站仍然失败，优先解释为：

- 网络异常
- 短时服务异常
- 或额度不足

而不是自动切回本地重模型。

---

## 4. 路由思想

这里参考 `z_ai-mcp-server` 的思路，不把所有图片都交给一份通用 prompt，而是先做轻量任务路由，再走对应分析模式。

当前建议的 `analysis_route` 定稿为：

- `general_image`
- `technical_diagram`
- `data_visualization`
- `form_like`
- `formula_like`
- `text_dense_visual`

含义：

### `general_image`

普通插图、照片、示意图、无法明确细分的图片。

### `technical_diagram`

架构图、流程图、模块关系图、框图。

### `data_visualization`

折线图、柱状图、散点图、热力图等图表类内容。

### `form_like`

问卷、申请表、信息登记页、字段密集型表单。

### `formula_like`

单个公式图、公式截图、符号密集型数学表达式。

### `text_dense_visual`

高文字密度截图、表格截图、扫描页局部块。

路由来源应优先使用上一步解析器已有的块类型和探针结果，而不是再用重逻辑二次猜。

---

## 5. 触发条件

当解析 PDF 的 pipeline 产出物中出现以下 `visual_type` 时，自动进入 VLM 队列：

- `image`
- `chart`
- `table_image`
- `formula_image`
- `form_image`
- `screenshot`
- `scan_crop`
- `unknown`

自动触发是默认行为，不需要手工点选某张图再分析。

但以下情况允许跳过：

- 图片路径不存在
- 图片导出损坏
- 明确被上游标记为装饰性噪声

被跳过的块必须记录为：

- `analysis_status = skipped`
- 同时进入 `extraction report`

---

## 6. 为什么当前不做多图批量

历史 `vlm_client.py` 证明过“批量调用有价值”，但当前版本不建议把多张图打进一个请求里。

这一版默认策略改为：

- 单图请求
- 异步并发
- 并发上限 `5`

原因很直接：

- 每张图和 `visual_block_id` 一一对应，最稳
- 失败重试不会污染其他图
- Markdown 回写不会因为批量结果错位而串图
- 表单、公式、图表混批时 prompt 更容易跑偏

因此当前阶段的请求模式定为：

- `request_mode = single-image-async`

批量模式留作后续优化项，而不是当前默认实现。

---

## 7. 请求编排流程

建议按以下顺序执行：

1. 上游解析器输出 `anchors + visual_blocks`
2. 为每个 `visual_block` 计算 `analysis_route`
3. 组装 VLM 请求上下文
4. 将任务放入异步队列
5. 使用最大并发 `5` 的 semaphore 调度
6. 每张图独立写回 `final_description`
7. 全部任务完成后，再统一生成最终 `markdown`
8. 生成 `structured json` 和 `extraction report`

这里有一个关键约束：

不要边拿到结果边直接改最终 Markdown 正文。

应先把结果写入 `visual_blocks`，最后再统一按照：

- `parent_anchor_id`
- `order_in_parent`

重建 Markdown。

这样能避免并发回写导致顺序漂移。

---

## 8. 单张图请求上下文

每次请求至少应携带这些上下文字段：

- `document_id`
- `visual_block_id`
- `visual_type`
- `analysis_route`
- `page`
- `heading_path`
- `caption_normalized`
- `nearby_text_excerpt`
- `image_rel_path`

其中：

- `caption_normalized` 是最重要的弱监督信号之一
- `nearby_text_excerpt` 帮模型知道这张图前后在讲什么
- `analysis_route` 决定用哪版提示词

输出目标当前只锁定一件事：

- 返回正常中文自然语言描述

不要求当前版本返回复杂 JSON。

JSON 化工作由中间件自己做，而不是把它完全外包给模型。

---

## 9. 提示词约束

提示词策略当前只锁三点：

1. 输出中文
2. 直接给描述，不寒暄
3. 不为了压缩长度而故意写得过短

同时遵守前面已经确定的回嵌风格：

- 不强制加“图片描述：”
- 不要求“图中展示了”作为固定前缀
- 对表单、公式、表格，允许自然地给出结构化语义描述

也就是说，prompt 应该追求“正常可读”，而不是“格式感很强”。

---

## 10. 重试策略

自动重试定稿如下：

- `max_retries = 3`
- 退避：指数退避 + 随机抖动

建议公式：

```text
delay(n) = base_delay_ms * 2^(n-1) + jitter_ms
```

其中建议初值：

- `base_delay_ms = 1000`
- `jitter_ms = random(0, 300)`

因此三次重试的大致节奏可理解为：

- 第 1 次失败后约 `1.xs`
- 第 2 次失败后约 `2.xs`
- 第 3 次失败后约 `4.xs`

这里不需要专门为 `429` 做额外特判逻辑设计，因为当前镜像站已经有负载均衡。

---

## 11. 什么错误值得重试

建议视为可重试：

- 网络抖动
- 请求超时
- `5xx`
- 返回体为空
- 返回内容明显不可用

建议视为不可重试或快速失败：

- `401 / 403`
- 模型名错误
- API key 缺失
- 图片文件本身不存在

如果无法明确分类，先按可重试处理，但最多只走到 `3` 次。

---

## 12. 降级策略

## 12.1 块级降级

如果某张图三次后仍失败，不阻断整篇文档主链。

默认块级处理：

- `analysis_status = degraded` 或 `failed`
- 原图路径保留
- 进入 `needs_review` 判定
- 仍然生成兜底 `markdown_line`

兜底文本建议按 `visual_type` 区分：

### 普通图片

```md
[此处包含一张图片，自动描述失败，建议结合原图查看。](images/xxx.jpg)
```

### 表单图片

```md
[此处包含表单图片，自动描述失败，建议结合原图查看。](images/xxx.jpg)
```

### 公式图片

```md
[此处包含公式图片，自动描述失败，建议结合原图查看。](images/xxx.jpg)
```

### 图表图片

```md
[此处包含图表，自动描述失败，建议结合原图查看。](images/xxx.jpg)
```

如果原图已有图注，图注仍然保留在上一行。

## 12.2 文档级降级

以下情况应把整篇导入标记为 `degraded`：

- 视觉块中有明显比例失败
- 表单 / 公式类图片连续失败
- Markdown 主体已生成，但视觉增强质量明显不稳

如果只是零星单图失败，而正文主链正常，可以保持文档总体 `ok`，同时把失败块写入 `warnings` 或 `needs_review_items`。

---

## 13. 人工复核触发条件

以下情况建议直接记入 `needs_review_items`：

- `form_like` 返回泛泛描述，看不出字段内容
- `formula_like` 返回过于空泛，看不出关系
- 连续多张图都只落了兜底文本
- 同一个 `parent_anchor` 下多图有明显串位风险
- 图注和描述明显冲突

这类风险应该体现在：

- `visual_blocks[].needs_review`
- `visual_blocks[].review_reason`
- `extraction_report.needs_review_items`

---

## 14. 与 OCR 的接口位

虽然当前默认不启用 `OCR`，但编排上要预留插槽。

推荐未来插入点：

1. 上游导出图片
2. 轻量路由
3. `OCR preprocess` 可选
4. `VLM enrich`
5. 结果融合
6. Markdown 回嵌

这意味着本轮的请求编排不要把数据结构设计成“只能接收纯图片、不能接收 OCR 文本”。

但当前版本产物里，不强制要求已有：

- `ocr_text`
- `merged_text`

---

## 15. 决策记录

- 选择外部 OpenAI 兼容 VLM，而不是本地重模型：因为当前目标是轻量化中间件
- 选择 `single-image-async + concurrency=5`，而不是多图批量：因为结果映射和回写更稳
- 选择 `3` 次自动重试 + 指数退避抖动：因为足够处理瞬时异常，同时不会把失败拖得太长
- 选择块级降级而不是整篇阻断：因为图片增强是 best-effort，不应拖死文本主链
- 选择先由中间件维护结构化字段，再让模型只产出自然语言描述：因为这样更可控

---

## 16. 相关文档

- [模块入口 README](./README.md)
- [VLM 图片理解与 Markdown 回嵌方案](./VLM图片理解与Markdown回嵌方案.md)
- [统一产物契约](./统一产物契约.md)
- [OCR、表单与公式增强方案](./OCR表单公式增强方案.md)
