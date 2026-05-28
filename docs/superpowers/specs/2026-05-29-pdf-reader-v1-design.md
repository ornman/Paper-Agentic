# PDF 阅读器 V1 设计规格 — 引用溯源阅读器

## 决策摘要

- **范围**: PRD Phase 1 (F1.1–F1.7)，严格分批交付
- **V1→V2 顺序推进**，V2 不提前开工
- **WPS 兼容优先**: 每个功能都验证 IIFE 构建不报错
- **subagent 并行**: V1 内部无依赖模块用 subagent 并行开发
- **PRD 文档**: `frontend/PRD-PDF-READER.md`

## 现状分析

`PdfReaderPanel.vue` (501 行) 当前能力:
- Canvas 位图渲染（不可选中/复制文字）
- 翻页按钮 + 页码输入（无连续滚动）
- `onScroll()` 空函数
- BUFFER=1（仅渲染当前 ± 1 页）
- 无目录、无快捷键、无引用高亮
- worker 用 `import.meta.url` 初始化（WPS 构建不兼容）

已有基础设施:
- `pdfjs-dist@^5.7.284` 已在 package.json
- UI store 有 readerOpen/readerPaperId/readerTargetPage
- 设计系统（CSS 变量、过渡、深色模式）就绪
- WPS IIFE 构建链完备

## 实施阶段

### 阶段 A: 基础层（顺序执行）

**F1.1 依赖修复**

| 任务 | 文件 | 说明 |
|------|------|------|
| pdfjs worker 初始化 | `composables/use-pdfjs.ts` | 单例，dev 用 import.meta.url，WPS 构建用 workerSrc='' |
| CMap 拷贝 | `public/cmaps/` | CJK 字体支持，从 pdfjs-dist 的 cmaps 目录拷贝 |
| vite 配置 | `vite.config.ts` | 确保 cmaps 目录被正确复制到 dist |

**WPS 兼容策略**:
- `use-pdfjs.ts` 导出 `getWorkerSrc()` 函数
- 检测 `typeof import.meta !== 'undefined' && import.meta.url`
- WPS IIFE 中 `import.meta` 不可用 → fallback `workerSrc = ''`（假 worker，主线程运行）

### 阶段 B: 核心渲染（B1 → B2 顺序）

**B1: F1.3 连续滚动 + 页码追踪**

新文件:
- `composables/use-pdf-renderer.ts`: IntersectionObserver、虚拟渲染（可见 ± 2 页）、canvas 内存管理
- `components/pdf-reader/PdfPage.vue`: 单页渲染生命周期（canvas 渲染 + 缩放同步）

改造 `PdfReaderPanel.vue`:
- `.reader-pages` 容器中为每页创建占位 `<div>`，高度由 `page.getViewport()` 预计算
- IntersectionObserver 追踪当前可见页 → 更新 currentPage
- 只渲染可见 ± 2 页的 Canvas，超出 ± 4 页的释放

**B2: F1.2 文本层**

改造 `PdfPage.vue`:
- 每页结构: `<div class="pdf-page"><canvas /><div class="textLayer" /></div>`
- 用 pdfjs `TextLayer` API 在 Canvas 上叠加透明文本层
- `::selection` 使用 `--color-accent-soft` 背景色
- 缩放时文本层同步缩放

### 阶段 C: UI 增强（B 完成后，C1/C2/C3 可并行）

**C1: F1.4 目录侧栏**

新文件:
- `components/pdf-reader/PdfOutline.vue`

功能:
- `pdfDoc.getOutline()` 获取书签树
- `dest` → 页码: `pdfDoc.getDestination()` → `pdfDoc.getPageIndex()`
- 缩进列表，点击跳转
- 宽屏 >800px: 固定 220px 侧栏
- 窄屏 420-800px: 覆盖式抽屉
- 切换动画 250ms `--ease-out-expo`

**C2: F1.5 键盘快捷键**

新文件:
- `composables/use-pdf-keyboard.ts`

| 快捷键 | 功能 |
|--------|------|
| ↑/↓ 或 j/k | 上下滚动一页 |
| +/- | 缩放 |
| Ctrl+F | 聚焦搜索（V1: 跳页） |
| Ctrl+Home/End | 首页/末页 |
| Escape | 关闭阅读器 |

**C3: F1.7 响应式布局**

| 断点 | 目录侧栏 | 工具栏 |
|------|----------|--------|
| >800px | 固定 220px 侧栏 | 完整显示 |
| 420-800px | 覆盖式抽屉 | 完整显示 |
| ≤420px (WPS) | 全宽覆盖抽屉 | 仅图标按钮 |

- ResizeObserver 监听容器变化
- 页面宽度跟随容器: `containerWidth - padding`

### 阶段 D: 引用高亮（依赖 C 完成）

**F1.6 引用高亮**

- UI store 新增 `readerHighlightText: string | null`
- 从 SourceCard.content（引用文本片段）在目标页 `getTextContent()` 中搜索匹配
- 匹配: 半透明蓝色矩形覆盖，3 秒后淡出
- 未匹配: 目标页边框闪烁

## 最终组件架构

```
src/components/pdf-reader/
  PdfReaderPanel.vue   ← 重构主面板（精简为布局容器）
  PdfPage.vue          ← 单页: canvas + textLayer + 高亮
  PdfOutline.vue       ← 目录侧栏
  PdfToolbar.vue       ← 工具栏（从主面板提取）

src/composables/
  use-pdfjs.ts         ← pdfjs 初始化单例
  use-pdf-keyboard.ts  ← 快捷键处理
  use-pdf-renderer.ts  ← 渲染核心: IntersectionObserver、虚拟渲染
```

## 横切关注点

### 性能

- IntersectionObserver 可见性追踪（非 scroll 轮询）
- 页面缓冲区: 可见 ± 2 页渲染，± 4 页外释放 Canvas 内存
- 缩放: 200ms 防抖
- 大文档（100+ 页）: 延迟获取 viewport，目录优先加载

### 动画

| 元素 | 进入 | 离开 | 曲线 |
|------|------|------|------|
| 阅读面板 | opacity 200ms | opacity 150ms | ease-out-expo |
| 目录侧栏 | translateX 250ms | translateX 200ms | ease-out-expo |
| 引用高亮 | fade-in 200ms | fade-out 3000ms | ease-out |
| 页面滚动 | smooth scroll 350ms | — | ease-out-expo |

### 无障碍

- `role="dialog"`, `aria-modal="true"`, focus trap
- 目录项 `role="treeitem"`
- 页码/缩放变更 `aria-live="polite"` 通知
- `prefers-reduced-motion` 禁用动画

### WPS 兼容

- 所有功能在 IIFE 构建中可用（无 ES Module 特性泄漏）
- worker 用假 worker 模式（主线程运行），性能降级可接受
- CMap 文件随构建输出到 dist/cmaps/

## Subagent 分工策略

| 阶段 | 可并行 | Subagent 分配 |
|------|--------|--------------|
| A | 否 | 主线程 |
| B | 否（B1→B2 有依赖） | 主线程 |
| C | 是 | C1/PdfOutline + C2/use-pdf-keyboard + C3/响应式 并行 |
| D | 否 | 主线程 |

## 验证清单

1. `pnpm dev` 启动 → 在 AI 对话点击引用 [N] → 跳转正确页面并高亮
2. 选中 PDF 文字 → Ctrl+C 复制到剪贴板
3. 打开目录侧栏 → 点击条目跳转
4. 缩放到 50%/200% → 文字选择仍然准确
5. 浏览器宽度拉到 400px → 窄屏布局正确
6. 键盘快捷键全部可操作
7. `pnpm build` → WPS 构建不报错
