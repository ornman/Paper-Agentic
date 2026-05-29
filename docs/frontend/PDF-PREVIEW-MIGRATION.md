# PDF 预览迁移方案：PDFPageView 替换手动 canvas + TextLayer

## 背景

当前 `PdfPage.vue` 手动组装 canvas 渲染 + TextLayer 文本层，导致文字选中和 canvas 对不齐。
这是 pdfjs 手动组装的固有缺陷（GitHub issues #14205, #14176, #20017 等）。

PDF.js 官方提供 `PDFPageView` 组件（Firefox 内置 PDF 阅读器用的），内部自动处理 canvas + text layer 对齐。
本次迁移用 `PDFPageView` 替换手动实现，保留公式、图片、矢量图等全部内容。

## 改动范围

| 文件 | 变更类型 |
|------|---------|
| `src/composables/pdf-event-bus.ts` | **新建** — EventBus 注入 key |
| `src/components/pdf-reader/PdfPage.vue` | **重写** — PDFPageView 替换手动渲染 |
| `src/components/PdfReaderPanel.vue` | **小改** — 创建 EventBus 并 provide |
| `src/composables/use-pdf-renderer.ts` | **不改** — 高度计算一致，无需变更 |
| `src/composables/use-pdfjs.ts` | **不改** — worker 初始化不受影响 |

## Step 1: 新建 `src/composables/pdf-event-bus.ts`

```typescript
import type { InjectionKey } from 'vue'
import type { EventBus } from 'pdfjs-dist/web/pdf_viewer.mjs'
export const PDF_EVENT_BUS_KEY: InjectionKey<EventBus> = Symbol('pdfEventBus')
```

## Step 2: PdfReaderPanel.vue — 创建并 provide EventBus

添加导入和 provide：

```typescript
import { EventBus } from 'pdfjs-dist/web/pdf_viewer.mjs'
import { PDF_EVENT_BUS_KEY } from '../composables/pdf-event-bus'

const eventBus = new EventBus()
provide(PDF_EVENT_BUS_KEY, eventBus)
```

## Step 3: PdfPage.vue — 重写核心渲染

### 3.1 模板简化

```html
<template>
  <div ref="containerRef" class="pdf-page-wrapper" />
</template>
```

PDFPageView 内部创建 canvas + textLayer + annotationLayer，不再需要手动写。

### 3.2 缩放模型（关键）

PDFPageView 内部将 scale 乘以 `PDF_TO_CSS_UNITS`（96/72 ≈ 1.333）。
为保持和现有行为一致，传入时除以这个因子：

```typescript
const PDF_TO_CSS_UNITS = 96 / 72  // 1.333

function adjustedScale() {
  return props.scale / PDF_TO_CSS_UNITS  // scale=1.0 → 传入 0.75 → 内算 0.75*1.333=1.0
}
```

验证：当前 `page.getViewport({ scale: 1.0 })` → US Letter 612×792px。
PDFPageView 传入 0.75 → 内部 `0.75 * 1.333 = 1.0` → 同样 612×792px。
`precomputeHeights()` 不需要改。

### 3.3 渲染生命周期

- **onMounted**: `getPage` → `new PDFPageView` → `setPdfPage` → append div → `draw()` → emit height
- **scale 变化**: `pageView.update({ scale })` → emit height
- **pageNumber/pdfDoc 变化**: destroy + 重新 createAndDraw
- **onBeforeUnmount**: `cancelRendering()` → `destroy()` → remove div

### 3.4 高亮保留

`highlightOnPage()` 逻辑不变，只是容器从 `containerRef` 改为 `pageView.div`。

### 3.5 CSS

- `pdf_viewer.css` 继续导入（PDFPageView 依赖其样式）
- 用 `:deep(.page)` 控制 PDFPageView 生成元素的视觉样式（白底、阴影、圆角）
- 保留高亮/闪烁动画 CSS 不变
- 删除不再需要的手动 canvas/text-layer 样式

## Step 4: 验证清单

1. `pnpm build` 确认构建通过，检查 bundle 大小
2. 启动 dev server，打开 demo PDF：
   - [ ] 文字选中是否对齐
   - [ ] 公式/图片是否正常渲染
   - [ ] 翻页（prev/next）是否正常
   - [ ] 目录跳转是否正常
   - [ ] 缩放是否正常
   - [ ] 引用高亮是否正常
3. 测试一篇真实论文 PDF（通过后端 `/api/v1/papers/{id}/open`）
