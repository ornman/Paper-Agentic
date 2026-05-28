# PDF 阅读器 V1 实施计划 — 引用溯源阅读器

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 PDF 阅读器从基础 Canvas 翻页器升级为支持文字选中/复制、连续滚动、目录导航、快捷键、引用高亮的完整阅读体验。

**Architecture:** 基于 pdfjs-dist 的文本层 + IntersectionObserver 虚拟渲染。将 PdfReaderPanel.vue 拆分为 PdfPage/PdfOutline/PdfToolbar 子组件，渲染逻辑提取到 composables。

**Tech Stack:** Vue 3 + TypeScript, pdfjs-dist ^5.7.284, Vite, WPS IIFE 构建

---

## File Structure

| 操作 | 文件 | 职责 |
|------|------|------|
| Create | `src/composables/use-pdfjs.ts` | pdfjs worker 初始化单例，WPS 兼容 |
| Create | `src/composables/use-pdf-renderer.ts` | IntersectionObserver、虚拟渲染、canvas 内存管理 |
| Create | `src/composables/use-pdf-keyboard.ts` | 键盘快捷键 |
| Create | `src/components/pdf-reader/PdfPage.vue` | 单页渲染：canvas + textLayer + 高亮 |
| Create | `src/components/pdf-reader/PdfOutline.vue` | 目录侧栏 |
| Create | `src/components/pdf-reader/PdfToolbar.vue` | 工具栏（从 PdfReaderPanel 提取） |
| Modify | `src/components/PdfReaderPanel.vue` | 重构为布局容器，调用子组件 |
| Modify | `src/stores/ui.ts` | 新增 readerHighlightText |
| Create | `public/cmaps/` | CJK 字体 CMap 文件（从 pdfjs-dist 拷贝） |

**不变更的文件：**
- `ChatView.vue` — PdfReaderPanel 的外部接口（props/events）保持不变
- `CitationPreview.vue` — 引用交互流程不变
- `vite.config.ts` — 已有 WPS 构建链，只需确保 cmaps 被复制

---

## 阶段 A: 基础层（顺序执行）

### Task 1: use-pdfjs.ts — worker 初始化单例

**Files:**
- Create: `frontend/src/composables/use-pdfjs.ts`

- [ ] **Step 1: 创建 use-pdfjs.ts composable**

```typescript
// frontend/src/composables/use-pdfjs.ts
import * as pdfjsLib from 'pdfjs-dist'

let initialized = false

function initWorker() {
  if (initialized) return
  initialized = true

  try {
    // Dev 模式：使用 import.meta.url 加载 worker
    if (typeof import.meta !== 'undefined' && import.meta.url) {
      pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
        'pdfjs-dist/build/pdf.worker.min.mjs',
        import.meta.url,
      ).toString()
    } else {
      // WPS IIFE 构建：假 worker，主线程运行
      pdfjsLib.GlobalWorkerOptions.workerSrc = ''
    }
  } catch {
    pdfjsLib.GlobalWorkerOptions.workerSrc = ''
  }
}

export function usePdfjs() {
  initWorker()
  return pdfjsLib
}
```

- [ ] **Step 2: 提交**

```bash
cd frontend
git add src/composables/use-pdfjs.ts
git commit -m "feat: 添加 use-pdfjs composable，WPS 兼容的 worker 初始化"
```

---

### Task 2: CMap 文件拷贝

**Files:**
- Create: `frontend/public/cmaps/` (从 pdfjs-dist 复制)

- [ ] **Step 1: 从 pdfjs-dist 复制 CMap 文件到 public/cmaps/**

```bash
cd frontend
# 找到 pdfjs-dist 的 cmaps 目录并复制
CPMAPS=$(node -e "console.log(require.resolve('pdfjs-dist/cmaps/__compressed_cmaps').replace('__compressed_cmaps',''))")
mkdir -p public/cmaps
cp "$CPMAPS"*.bcmap public/cmaps/
```

如果上面的路径不对，备选方案：
```bash
CPMAPS=$(node -e "console.log(require('path').dirname(require.resolve('pdfjs-dist/package.json')) + '/cmaps/')")
mkdir -p public/cmaps
cp "$CPMAPS"*.bcmap public/cmaps/
```

验证：`ls public/cmaps/ | head -5` 应显示 `.bcmap` 文件。

- [ ] **Step 2: 在 use-pdfjs.ts 中配置 CMap 路径**

在 `use-pdfjs.ts` 的 `usePdfjs()` 返回值中添加 cMapUrl 配置辅助：

```typescript
export function usePdfjs() {
  initWorker()
  return {
    lib: pdfjsLib,
    /** 传给 getDocument 的 CMap 配置 */
    cMapOptions: {
      cMapUrl: '/cmaps/',
      cMapPacked: true,
    },
  }
}
```

更新函数签名的返回类型（完整文件）：

```typescript
import * as pdfjsLib from 'pdfjs-dist'

let initialized = false

function initWorker() {
  if (initialized) return
  initialized = true

  try {
    if (typeof import.meta !== 'undefined' && import.meta.url) {
      pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
        'pdfjs-dist/build/pdf.worker.min.mjs',
        import.meta.url,
      ).toString()
    } else {
      pdfjsLib.GlobalWorkerOptions.workerSrc = ''
    }
  } catch {
    pdfjsLib.GlobalWorkerOptions.workerSrc = ''
  }
}

export function usePdfjs() {
  initWorker()
  return {
    lib: pdfjsLib,
    cMapOptions: {
      cMapUrl: '/cmaps/',
      cMapPacked: true,
    } as const,
  }
}
```

- [ ] **Step 3: 提交**

```bash
cd frontend
git add public/cmaps/ src/composables/use-pdfjs.ts
git commit -m "feat: 添加 CJK CMap 文件支持"
```

---

### Task 3: 更新 PdfReaderPanel.vue 使用 use-pdfjs

**Files:**
- Modify: `frontend/src/components/PdfReaderPanel.vue`

- [ ] **Step 1: 替换 worker 初始化和 getDocument 调用**

在 `<script setup>` 顶部，替换：
```typescript
// 删除这 3 行：
import * as pdfjsLib from 'pdfjs-dist'
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url
).toString()
```

替换为：
```typescript
import { usePdfjs } from '../composables/use-pdfjs'

const { lib: pdfjsLib, cMapOptions } = usePdfjs()
```

在 `loadPdf()` 函数中，替换 `getDocument` 调用：
```typescript
// 替换前：
const loadingTask = pdfjsLib.getDocument(url)

// 替换后：
const loadingTask = pdfjsLib.getDocument({
  url,
  ...cMapOptions,
})
```

- [ ] **Step 2: 验证 dev server 正常**

```bash
cd frontend
pnpm dev
# 在浏览器打开，点击引用打开 PDF 阅读器，确认 PDF 正常渲染
```

- [ ] **Step 3: 提交**

```bash
cd frontend
git add src/components/PdfReaderPanel.vue
git commit -m "refactor: PdfReaderPanel 使用 use-pdfjs composable"
```

---

## 阶段 B: 核心渲染

### Task 4: PdfPage.vue — 单页渲染组件

**Files:**
- Create: `frontend/src/components/pdf-reader/PdfPage.vue`

这是单页渲染的基础组件，负责 canvas 渲染。后续 Task 会添加 textLayer。

- [ ] **Step 1: 创建 pdf-reader 目录和 PdfPage.vue**

```bash
mkdir -p frontend/src/components/pdf-reader
```

```vue
<!-- frontend/src/components/pdf-reader/PdfPage.vue -->
<template>
  <div
    ref="containerRef"
    class="pdf-page"
    :data-page-number="pageNumber"
  >
    <canvas ref="canvasRef" class="pdf-page-canvas" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'
import type { PDFDocumentProxy, PDFPageProxy } from 'pdfjs-dist'

const props = defineProps<{
  pdfDoc: PDFDocumentProxy
  pageNumber: number
  scale: number
  containerWidth: number
}>()

const emit = defineEmits<{
  (e: 'page-height', height: number): void
}>()

const containerRef = ref<HTMLDivElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)

let renderTask: { promise: Promise<void>; cancel(): void } | null = null
let pageProxy: PDFPageProxy | null = null

async function render() {
  if (!canvasRef.value) return

  // 取消进行中的渲染
  if (renderTask) {
    renderTask.cancel()
    renderTask = null
  }

  try {
    pageProxy = await props.pdfDoc.getPage(props.pageNumber)
    const dpr = window.devicePixelRatio || 1
    const viewport = pageProxy.getViewport({ scale: props.scale * dpr })
    const canvas = canvasRef.value

    canvas.width = viewport.width
    canvas.height = viewport.height
    canvas.style.width = `${Math.floor(viewport.width / dpr)}px`
    canvas.style.height = `${Math.floor(viewport.height / dpr)}px`

    // 通知父组件此页高度（用于占位）
    emit('page-height', Math.floor(viewport.height / dpr))

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    renderTask = pageProxy.render({ canvasContext: ctx, viewport })
    await renderTask.promise
  } catch (e: unknown) {
    // RenderingCancelledException 是正常的，忽略
    if (e instanceof Error && e.name === 'RenderingCancelledException') return
    console.error(`Page ${props.pageNumber} render error:`, e)
  } finally {
    renderTask = null
  }
}

watch(
  () => [props.pdfDoc, props.pageNumber, props.scale] as const,
  () => render(),
  { immediate: true },
)

onBeforeUnmount(() => {
  if (renderTask) {
    renderTask.cancel()
    renderTask = null
  }
  pageProxy?.cleanup()
})
</script>

<style scoped>
.pdf-page {
  position: relative;
  background: white;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  border-radius: 2px;
  margin: 0 auto;
}

.pdf-page-canvas {
  display: block;
}
</style>
```

- [ ] **Step 2: 提交**

```bash
cd frontend
git add src/components/pdf-reader/PdfPage.vue
git commit -m "feat: 创建 PdfPage 单页渲染组件"
```

---

### Task 5: use-pdf-renderer.ts — 虚拟渲染 + 连续滚动

**Files:**
- Create: `frontend/src/composables/use-pdf-renderer.ts`

这个 composable 管理页面高度的预计算、IntersectionObserver 页码追踪、虚拟渲染缓冲区。

- [ ] **Step 1: 创建 use-pdf-renderer.ts**

```typescript
// frontend/src/composables/use-pdf-renderer.ts
import { ref, watch, onBeforeUnmount, type Ref } from 'vue'
import type { PDFDocumentProxy } from 'pdfjs-dist'

export function usePdfRenderer(
  pdfDoc: Ref<PDFDocumentProxy | null>,
  scale: Ref<number>,
) {
  const currentPage = ref(1)
  const totalPages = ref(0)
  const pageHeights = ref<number[]>([])
  const visiblePages = ref<Set<number>>(new Set())

  const BUFFER_BEFORE = 2
  const BUFFER_AFTER = 2

  /** 需要渲染的页面集合：可见 ± buffer */
  const pagesToRender = ref<number[]>([])

  let observer: IntersectionObserver | null = null
  const pageElements = new Map<number, HTMLElement>()

  /** 加载 PDF 后初始化 */
  function init(doc: PDFDocumentProxy) {
    totalPages.value = doc.numPages
    currentPage.value = 1
    pageHeights.value = []
    precomputeHeights(doc)
  }

  /** 预计算每页高度 */
  async function precomputeHeights(doc: PDFDocumentProxy) {
    const heights: number[] = []
    // 只获取第一页来确定基准比例，然后按比例估算
    // 大文档延迟加载：一次只处理一批
    const batchSize = 10
    for (let i = 1; i <= doc.numPages; i += batchSize) {
      const batch = []
      for (let j = i; j <= Math.min(i + batchSize - 1, doc.numPages); j++) {
        batch.push(doc.getPage(j))
      }
      const pages = await Promise.all(batch)
      for (const page of pages) {
        const vp = page.getViewport({ scale: scale.value })
        heights.push(vp.height / (window.devicePixelRatio || 1))
      }
    }
    pageHeights.value = heights
  }

  /** 注册页面 DOM 元素到 IntersectionObserver */
  function setupObserver(scrollContainer: HTMLElement) {
    teardownObserver()

    observer = new IntersectionObserver(
      (entries) => {
        let topPage = currentPage.value
        let topY = Infinity

        for (const entry of entries) {
          const pageNum = Number(entry.target.getAttribute('data-page-number'))
          if (isNaN(pageNum)) continue

          if (entry.isIntersecting) {
            visiblePages.value.add(pageNum)
            // 追踪最靠上的可见页作为当前页
            if (entry.boundingClientRect.top < topY) {
              topY = entry.boundingClientRect.top
              topPage = pageNum
            }
          } else {
            visiblePages.value.delete(pageNum)
          }
        }

        if (topPage !== currentPage.value) {
          currentPage.value = topPage
        }

        updatePagesToRender()
      },
      {
        root: scrollContainer,
        threshold: 0.1,
      },
    )

    // 观察已注册的页面元素
    for (const el of pageElements.values()) {
      observer.observe(el)
    }
  }

  function registerPage(pageNum: number, el: HTMLElement) {
    pageElements.set(pageNum, el)
    observer?.observe(el)
  }

  function unregisterPage(pageNum: number) {
    const el = pageElements.get(pageNum)
    if (el) {
      observer?.unobserve(el)
      pageElements.delete(pageNum)
    }
  }

  function teardownObserver() {
    if (observer) {
      for (const el of pageElements.values()) {
        observer.unobserve(el)
      }
      observer.disconnect()
      observer = null
    }
    pageElements.clear()
    visiblePages.value.clear()
  }

  function updatePagesToRender() {
    const pages = new Set<number>()
    const visible = Array.from(visiblePages.value)

    if (visible.length === 0) {
      // 没有可见页时至少渲染当前页附近
      for (
        let i = Math.max(1, currentPage.value - BUFFER_BEFORE);
        i <= Math.min(totalPages.value, currentPage.value + BUFFER_AFTER);
        i++
      ) {
        pages.add(i)
      }
    } else {
      for (const vp of visible) {
        for (
          let i = Math.max(1, vp - BUFFER_BEFORE);
          i <= Math.min(totalPages.value, vp + BUFFER_AFTER);
          i++
        ) {
          pages.add(i)
        }
      }
    }

    pagesToRender.value = Array.from(pages).sort((a, b) => a - b)
  }

  /** 滚动到指定页面 */
  function scrollToPage(pageNum: number) {
    if (pageNum < 1 || pageNum > totalPages.value) return
    const el = pageElements.get(pageNum)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
    currentPage.value = pageNum
  }

  /** 缩放变化时重新计算高度 */
  watch(scale, async () => {
    if (pdfDoc.value) {
      await precomputeHeights(pdfDoc.value)
    }
  })

  onBeforeUnmount(() => {
    teardownObserver()
  })

  return {
    currentPage,
    totalPages,
    pageHeights,
    pagesToRender,
    visiblePages,
    init,
    setupObserver,
    registerPage,
    unregisterPage,
    scrollToPage,
  }
}
```

- [ ] **Step 2: 提交**

```bash
cd frontend
git add src/composables/use-pdf-renderer.ts
git commit -m "feat: 添加 use-pdf-renderer composable，IntersectionObserver 虚拟渲染"
```

---

### Task 6: 重构 PdfReaderPanel — 连续滚动

**Files:**
- Modify: `frontend/src/components/PdfReaderPanel.vue`

这是最大的改造：从翻页模式改为连续滚动，集成 use-pdf-renderer 和 PdfPage。

- [ ] **Step 1: 重写 PdfReaderPanel.vue 的 script 和 template**

替换整个 `<script setup>` 和 `<template>` 为：

```vue
<!-- frontend/src/components/PdfReaderPanel.vue -->
<template>
  <Teleport to="body">
    <Transition name="reader-backdrop">
      <div
        v-if="visible"
        class="reader-backdrop"
        @click="emit('close')"
      />
    </Transition>

    <Transition name="reader-panel">
      <div
        v-if="visible"
        class="reader-panel"
        role="dialog"
        aria-modal="true"
        aria-label="PDF 阅读面板"
        tabindex="-1"
        @keydown.escape="emit('close')"
      >
        <!-- Toolbar -->
        <div class="reader-toolbar">
          <div class="reader-title" :title="paperTitle">{{ paperTitle }}</div>

          <div class="reader-controls">
            <button
              class="reader-btn"
              :disabled="renderer.currentPage.value <= 1"
              aria-label="上一页"
              @click="renderer.scrollToPage(renderer.currentPage.value - 1)"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
            </button>

            <span class="reader-page-info">
              <input
                ref="pageInputRef"
                class="reader-page-input"
                type="number"
                :value="renderer.currentPage.value"
                :min="1"
                :max="renderer.totalPages.value"
                @keydown.enter="handlePageInput"
                @blur="handlePageInput"
              />
              <span class="reader-page-sep">/</span>
              <span>{{ renderer.totalPages.value }}</span>
            </span>

            <button
              class="reader-btn"
              :disabled="renderer.currentPage.value >= renderer.totalPages.value"
              aria-label="下一页"
              @click="renderer.scrollToPage(renderer.currentPage.value + 1)"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
            </button>

            <span class="reader-divider" />

            <button
              class="reader-btn"
              :disabled="scale <= 0.5"
              aria-label="缩小"
              @click="setScale(Math.max(0.5, scale - 0.25))"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="5" y1="12" x2="19" y2="12"/></svg>
            </button>

            <span class="reader-scale-label">{{ Math.round(scale * 100) }}%</span>

            <button
              class="reader-btn"
              :disabled="scale >= 3"
              aria-label="放大"
              @click="setScale(Math.min(3, scale + 0.25))"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            </button>
          </div>

          <button
            class="reader-close-btn"
            type="button"
            aria-label="关闭阅读面板"
            @click="emit('close')"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <!-- PDF viewport -->
        <div ref="scrollContainerRef" class="reader-body">
          <div v-if="loading" class="reader-loading">
            <div class="reader-spinner" />
            <span>加载中…</span>
          </div>
          <div v-else-if="error" class="reader-error">
            <span>{{ error }}</span>
            <button class="reader-btn" @click="loadPdf">重试</button>
          </div>
          <div v-else-if="pdfDocProxy" class="reader-pages">
            <div
              v-for="pageNum in renderer.totalPages.value"
              :key="pageNum"
              :data-page-number="pageNum"
              class="reader-page-slot"
              :style="{ height: renderer.pageHeights.value[pageNum - 1] + 'px' }"
            >
              <PdfPage
                v-if="renderer.pagesToRender.value.includes(pageNum)"
                :pdf-doc="pdfDocProxy"
                :page-number="pageNum"
                :scale="scale"
                :container-width="containerWidth"
                @page-height="(h) => onPageHeight(pageNum, h)"
              />
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onBeforeUnmount, computed } from 'vue'
import type { PDFDocumentProxy } from 'pdfjs-dist'
import { usePdfjs } from '../composables/use-pdfjs'
import { usePdfRenderer } from '../composables/use-pdf-renderer'
import { buildPaperOpenUrl } from '../services/library-api'
import PdfPage from './pdf-reader/PdfPage.vue'

const { lib: pdfjsLib, cMapOptions } = usePdfjs()

const props = defineProps<{
  visible: boolean
  paperId: string
  targetPage?: number
  demoMode?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const pageInputRef = ref<HTMLInputElement | null>(null)
const scrollContainerRef = ref<HTMLElement | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const paperTitle = ref('PDF 阅读器')
const scale = ref(1.0)
const containerWidth = ref(480)

let pdfDocProxy: PDFDocumentProxy | null = null

const renderer = usePdfRenderer(
  computed(() => pdfDocProxy),
  scale,
)

function onPageHeight(pageNum: number, height: number) {
  if (renderer.pageHeights.value[pageNum - 1] !== height) {
    renderer.pageHeights.value[pageNum - 1] = height
  }
}

function setScale(next: number) {
  scale.value = next
}

async function loadPdf() {
  if (!props.paperId) return

  loading.value = true
  error.value = null
  pdfDocProxy = null
  renderer.totalPages.value = 0
  renderer.currentPage.value = 1

  try {
    const isDemo = props.demoMode || props.paperId.startsWith('paper-')
    const url = isDemo ? '/demo-paper.pdf' : buildPaperOpenUrl(props.paperId)
    const loadingTask = pdfjsLib.getDocument({ url, ...cMapOptions })
    pdfDocProxy = await loadingTask.promise
    paperTitle.value = isDemo ? 'Demo PDF' : `PDF (${props.paperId.slice(0, 8)}…)`

    renderer.init(pdfDocProxy)

    if (props.targetPage && props.targetPage >= 1 && props.targetPage <= pdfDocProxy.numPages) {
      renderer.currentPage.value = props.targetPage
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'PDF 加载失败'
  } finally {
    loading.value = false
  }
}

function handlePageInput() {
  const val = parseInt(pageInputRef.value?.value ?? '', 10)
  if (!isNaN(val)) renderer.scrollToPage(val)
}

watch(() => props.visible, async (visible) => {
  if (visible && props.paperId) {
    await loadPdf()
    await nextTick()
    if (scrollContainerRef.value && pdfDocProxy) {
      renderer.setupObserver(scrollContainerRef.value)
    }
    // 如果有 targetPage，滚动到对应页
    if (props.targetPage && props.targetPage >= 1) {
      await nextTick()
      renderer.scrollToPage(props.targetPage)
    }
  } else {
    pdfDocProxy?.destroy()
    pdfDocProxy = null
  }
})

onBeforeUnmount(() => {
  pdfDocProxy?.destroy()
  pdfDocProxy = null
})
</script>
```

**保留现有 CSS 不变**，只添加新样式：

```css
/* 追加到 <style scoped> 末尾 */
.reader-page-slot {
  display: flex;
  justify-content: center;
  margin-bottom: var(--space-3);
}
```

- [ ] **Step 2: 验证连续滚动工作**

```bash
cd frontend
pnpm dev
# 打开 PDF 阅读器，确认：
# 1. 所有页面用占位 div 撑开正确高度
# 2. 滚动时页码自动更新
# 3. 只有可见 ± 2 页被渲染
```

- [ ] **Step 3: 提交**

```bash
cd frontend
git add src/components/PdfReaderPanel.vue
git commit -m "feat: PdfReaderPanel 改为连续滚动模式，集成 use-pdf-renderer + PdfPage"
```

---

### Task 7: PdfPage.vue 添加文本层

**Files:**
- Modify: `frontend/src/components/pdf-reader/PdfPage.vue`

- [ ] **Step 1: 在 PdfPage.vue 中添加 TextLayer**

在 template 中添加 textLayer div：

```html
<template>
  <div
    ref="containerRef"
    class="pdf-page"
    :data-page-number="pageNumber"
  >
    <canvas ref="canvasRef" class="pdf-page-canvas" />
    <div ref="textLayerRef" class="pdf-text-layer" />
  </div>
</template>
```

在 script 中添加 TextLayer 渲染逻辑。更新完整 script：

```typescript
<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'
import { TextLayer } from 'pdfjs-dist'
import type { PDFDocumentProxy, PDFPageProxy } from 'pdfjs-dist'

const props = defineProps<{
  pdfDoc: PDFDocumentProxy
  pageNumber: number
  scale: number
  containerWidth: number
}>()

const emit = defineEmits<{
  (e: 'page-height', height: number): void
}>()

const containerRef = ref<HTMLDivElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const textLayerRef = ref<HTMLDivElement | null>(null)

let renderTask: { promise: Promise<void>; cancel(): void } | null = null
let pageProxy: PDFPageProxy | null = null

async function render() {
  if (!canvasRef.value) return

  if (renderTask) {
    renderTask.cancel()
    renderTask = null
  }

  try {
    pageProxy = await props.pdfDoc.getPage(props.pageNumber)
    const dpr = window.devicePixelRatio || 1
    const viewport = pageProxy.getViewport({ scale: props.scale * dpr })
    const displayViewport = pageProxy.getViewport({ scale: props.scale })
    const canvas = canvasRef.value

    canvas.width = viewport.width
    canvas.height = viewport.height
    canvas.style.width = `${Math.floor(displayViewport.width)}px`
    canvas.style.height = `${Math.floor(displayViewport.height)}px`

    emit('page-height', Math.floor(displayViewport.height))

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    renderTask = pageProxy.render({ canvasContext: ctx, viewport })
    await renderTask.promise

    // 渲染文本层
    await renderTextLayer(pageProxy, displayViewport)
  } catch (e: unknown) {
    if (e instanceof Error && e.name === 'RenderingCancelledException') return
    console.error(`Page ${props.pageNumber} render error:`, e)
  } finally {
    renderTask = null
  }
}

async function renderTextLayer(page: PDFPageProxy, viewport: { width: number; height: number; scale: number }) {
  if (!textLayerRef.value) return

  const textContent = await page.getTextContent()
  const textLayer = new TextLayer({
    textContentSource: textContent,
    container: textLayerRef.value,
    viewport,
  })
  await textLayer.render()
}

watch(
  () => [props.pdfDoc, props.pageNumber, props.scale] as const,
  () => render(),
  { immediate: true },
)

onBeforeUnmount(() => {
  if (renderTask) {
    renderTask.cancel()
    renderTask = null
  }
  pageProxy?.cleanup()
})
</script>
```

添加文本层 CSS：

```css
<style scoped>
.pdf-page {
  position: relative;
  background: white;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  border-radius: 2px;
  margin: 0 auto;
}

.pdf-page-canvas {
  display: block;
}

.pdf-text-layer {
  position: absolute;
  inset: 0;
  overflow: hidden;
  opacity: 0.25;
  line-height: 1;
}

.pdf-text-layer ::selection {
  background: var(--color-accent-soft);
}

.pdf-text-layer > span {
  color: transparent;
  position: absolute;
  white-space: pre;
  transform-origin: 0% 0%;
}
</style>
```

- [ ] **Step 2: 验证文字选中/复制**

```bash
cd frontend
pnpm dev
# 打开 PDF 阅读器，确认：
# 1. 鼠标悬停在文字上时光标变为文本选择
# 2. 可以拖选文字
# 3. Ctrl+C 复制到剪贴板
# 4. 缩放后文本层同步
```

- [ ] **Step 3: 提交**

```bash
cd frontend
git add src/components/pdf-reader/PdfPage.vue
git commit -m "feat: PdfPage 添加文本层，支持文字选中/复制"
```

---

## 阶段 C: UI 增强（C1/C2 可并行）

### Task 8: PdfToolbar.vue — 提取工具栏

**Files:**
- Create: `frontend/src/components/pdf-reader/PdfToolbar.vue`
- Modify: `frontend/src/components/PdfReaderPanel.vue`

- [ ] **Step 1: 创建 PdfToolbar.vue**

```vue
<!-- frontend/src/components/pdf-reader/PdfToolbar.vue -->
<template>
  <div class="reader-toolbar">
    <div class="reader-title" :title="title">{{ title }}</div>

    <div class="reader-controls">
      <button
        class="reader-btn"
        :disabled="currentPage <= 1"
        aria-label="上一页"
        @click="emit('prev')"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
      </button>

      <span class="reader-page-info">
        <input
          ref="pageInputRef"
          class="reader-page-input"
          type="number"
          :value="currentPage"
          :min="1"
          :max="totalPages"
          @keydown.enter="handlePageInput"
          @blur="handlePageInput"
        />
        <span class="reader-page-sep">/</span>
        <span>{{ totalPages }}</span>
      </span>

      <button
        class="reader-btn"
        :disabled="currentPage >= totalPages"
        aria-label="下一页"
        @click="emit('next')"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
      </button>

      <span class="reader-divider" />

      <button
        class="reader-btn"
        :disabled="scale <= 0.5"
        aria-label="缩小"
        @click="emit('zoom-out')"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="5" y1="12" x2="19" y2="12"/></svg>
      </button>

      <span class="reader-scale-label">{{ Math.round(scale * 100) }}%</span>

      <button
        class="reader-btn"
        :disabled="scale >= 3"
        aria-label="放大"
        @click="emit('zoom-in')"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
      </button>

      <template v-if="showOutlineButton">
        <span class="reader-divider" />
        <button
          class="reader-btn"
          :class="{ 'reader-btn-active': outlineOpen }"
          aria-label="目录"
          @click="emit('toggle-outline')"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="8" y1="6" x2="21" y2="6"/>
            <line x1="8" y1="12" x2="21" y2="12"/>
            <line x1="8" y1="18" x2="21" y2="18"/>
            <line x1="3" y1="6" x2="3.01" y2="6"/>
            <line x1="3" y1="12" x2="3.01" y2="12"/>
            <line x1="3" y1="18" x2="3.01" y2="18"/>
          </svg>
        </button>
      </template>
    </div>

    <button
      class="reader-close-btn"
      type="button"
      aria-label="关闭阅读面板"
      @click="emit('close')"
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="6" x2="6" y2="18" />
        <line x1="6" y1="6" x2="18" y2="18" />
      </svg>
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  title: string
  currentPage: number
  totalPages: number
  scale: number
  outlineOpen: boolean
  showOutlineButton: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'prev'): void
  (e: 'next'): void
  (e: 'zoom-in'): void
  (e: 'zoom-out'): void
  (e: 'go-to-page', page: number): void
  (e: 'toggle-outline'): void
}>()

const pageInputRef = ref<HTMLInputElement | null>(null)

function handlePageInput() {
  const val = parseInt(pageInputRef.value?.value ?? '', 10)
  if (!isNaN(val)) emit('go-to-page', val)
}
</script>

<style scoped>
.reader-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border-subtle);
  flex-shrink: 0;
}

.reader-title {
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 80px;
  max-width: 300px;
}

.reader-controls {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex: 1;
  justify-content: center;
}

.reader-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  transition: background 0.15s, color 0.15s;
}

.reader-btn:hover:not(:disabled) {
  background: var(--color-surface-muted);
  color: var(--color-text-primary);
}

.reader-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.reader-btn-active {
  background: var(--color-accent-soft);
  color: var(--color-accent);
}

.reader-page-info {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  font-variant-numeric: tabular-nums;
}

.reader-page-input {
  width: 36px;
  text-align: center;
  font-size: var(--font-size-sm);
  font-variant-numeric: tabular-nums;
  color: var(--color-text-primary);
  background: var(--color-surface-muted);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  padding: 2px 0;
  outline: none;
  transition: border-color 0.15s;
}

.reader-page-input:focus {
  border-color: var(--color-accent);
}

.reader-page-input::-webkit-inner-spin-button,
.reader-page-input::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.reader-page-input[type='number'] {
  -moz-appearance: textfield;
}

.reader-page-sep {
  color: var(--color-text-muted);
}

.reader-divider {
  width: 1px;
  height: 16px;
  background: var(--color-border-subtle);
  margin: 0 var(--space-1);
}

.reader-scale-label {
  font-size: 11px;
  color: var(--color-text-muted);
  font-variant-numeric: tabular-nums;
  min-width: 36px;
  text-align: center;
}

.reader-close-btn {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  transition: background 0.15s, color 0.15s;
  flex-shrink: 0;
}

.reader-close-btn:hover {
  background: var(--color-surface-muted);
  color: var(--color-text-primary);
}
</style>
```

- [ ] **Step 2: 更新 PdfReaderPanel.vue 使用 PdfToolbar**

在 PdfReaderPanel.vue 中：
- 导入 PdfToolbar 组件
- 替换 `<div class="reader-toolbar">` 整块为 `<PdfToolbar>` 组件调用

```typescript
// 添加 import
import PdfToolbar from './pdf-reader/PdfToolbar.vue'
```

template 中的工具栏区域替换为：

```html
<PdfToolbar
  :title="paperTitle"
  :current-page="renderer.currentPage.value"
  :total-pages="renderer.totalPages.value"
  :scale="scale"
  :outline-open="outlineOpen"
  :show-outline-button="hasOutline"
  @close="emit('close')"
  @prev="renderer.scrollToPage(renderer.currentPage.value - 1)"
  @next="renderer.scrollToPage(renderer.currentPage.value + 1)"
  @zoom-in="setScale(Math.min(3, scale + 0.25))"
  @zoom-out="setScale(Math.max(0.5, scale - 0.25))"
  @go-to-page="renderer.scrollToPage"
  @toggle-outline="outlineOpen = !outlineOpen"
/>
```

在 script 中添加状态：

```typescript
const outlineOpen = ref(false)
const hasOutline = ref(false)
```

- [ ] **Step 3: 提交**

```bash
cd frontend
git add src/components/pdf-reader/PdfToolbar.vue src/components/PdfReaderPanel.vue
git commit -m "refactor: 提取 PdfToolbar 组件，PdfReaderPanel 使用子组件"
```

---

### Task 9: PdfOutline.vue — 目录侧栏

**Files:**
- Create: `frontend/src/components/pdf-reader/PdfOutline.vue`
- Modify: `frontend/src/components/PdfReaderPanel.vue`

- [ ] **Step 1: 创建 PdfOutline.vue**

```vue
<!-- frontend/src/components/pdf-reader/PdfOutline.vue -->
<template>
  <Transition name="outline-sidebar">
    <div
      v-if="open"
      class="outline-sidebar"
      role="navigation"
      aria-label="PDF 目录"
    >
      <div class="outline-header">
        <span class="outline-title">目录</span>
        <button
          class="outline-close-btn"
          aria-label="关闭目录"
          @click="emit('close')"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <div v-if="items.length === 0" class="outline-empty">
        此文档无目录
      </div>

      <ul v-else class="outline-list" role="tree">
        <PdfOutlineItem
          v-for="(item, index) in items"
          :key="index"
          :item="item"
          :depth="0"
          @navigate="handleNavigate"
        />
      </ul>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import PdfOutlineItem from './PdfOutlineItem.vue'

export interface OutlineItem {
  title: string
  dest: unknown
  items: OutlineItem[]
  pageNumber?: number
}

defineProps<{
  open: boolean
  items: OutlineItem[]
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'navigate', pageNumber: number): void
}>()

function handleNavigate(pageNumber: number) {
  emit('navigate', pageNumber)
}
</script>

<style scoped>
.outline-sidebar {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 220px;
  background: var(--color-surface-card);
  border-right: 1px solid var(--color-border-subtle);
  display: flex;
  flex-direction: column;
  z-index: 10;
  overflow: hidden;
}

.outline-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border-subtle);
  flex-shrink: 0;
}

.outline-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-primary);
}

.outline-close-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  transition: background 0.15s;
}

.outline-close-btn:hover {
  background: var(--color-surface-muted);
}

.outline-empty {
  padding: var(--space-4);
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  text-align: center;
}

.outline-list {
  list-style: none;
  overflow-y: auto;
  flex: 1;
  padding: var(--space-2) 0;
}

/* 过渡动画 */
.outline-sidebar-enter-active {
  transition: transform 250ms var(--ease-out-expo);
}
.outline-sidebar-leave-active {
  transition: transform 200ms ease-in-out;
}
.outline-sidebar-enter-from,
.outline-sidebar-leave-to {
  transform: translateX(-100%);
}

/* 窄屏覆盖模式 */
@media (max-width: 800px) {
  .outline-sidebar {
    position: fixed;
    z-index: 220;
    box-shadow: var(--shadow-drawer);
  }
}

@media (max-width: 420px) {
  .outline-sidebar {
    width: 100%;
  }
}
</style>
```

- [ ] **Step 2: 创建 PdfOutlineItem.vue（递归子项）**

```vue
<!-- frontend/src/components/pdf-reader/PdfOutlineItem.vue -->
<template>
  <li role="treeitem" :style="{ paddingLeft: depth * 16 + 'px' }">
    <button
      class="outline-item-btn"
      @click="emit('navigate', item.pageNumber ?? 1)"
    >
      {{ item.title }}
    </button>
    <ul v-if="item.items.length > 0" role="group">
      <PdfOutlineItem
        v-for="(child, index) in item.items"
        :key="index"
        :item="child"
        :depth="depth + 1"
        @navigate="(p: number) => emit('navigate', p)"
      />
    </ul>
  </li>
</template>

<script setup lang="ts">
import type { OutlineItem } from './PdfOutline.vue'

defineProps<{
  item: OutlineItem
  depth: number
}>()

const emit = defineEmits<{
  (e: 'navigate', pageNumber: number): void
}>()
</script>

<style scoped>
ul {
  list-style: none;
}

.outline-item-btn {
  display: block;
  width: 100%;
  text-align: left;
  padding: 6px 12px;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  border-radius: var(--radius-sm);
  transition: background 0.15s, color 0.15s;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.outline-item-btn:hover {
  background: var(--color-surface-muted);
  color: var(--color-text-primary);
}
</style>
```

- [ ] **Step 3: 在 PdfReaderPanel.vue 中集成目录**

添加导入：

```typescript
import PdfOutline from './pdf-reader/PdfOutline.vue'
import type { OutlineItem } from './pdf-reader/PdfOutline.vue'
```

添加状态和函数：

```typescript
const outlineItems = ref<OutlineItem[]>([])

async function loadOutline() {
  if (!pdfDocProxy) return
  const rawOutline = await pdfDocProxy.getOutline()
  if (!rawOutline || rawOutline.length === 0) {
    hasOutline.value = false
    outlineItems.value = []
    return
  }
  hasOutline.value = true

  const items: OutlineItem[] = []
  for (const raw of rawOutline) {
    items.push(await resolveOutlineItem(raw))
  }
  outlineItems.value = items
}

async function resolveOutlineItem(raw: { title: string; dest: unknown; items: unknown[] }): Promise<OutlineItem> {
  let pageNumber: number | undefined
  try {
    let dest = raw.dest
    if (typeof dest === 'string') {
      dest = await pdfDocProxy!.getDestination(dest)
    }
    if (Array.isArray(dest) && dest.length > 0) {
      const pageIdx = await pdfDocProxy!.getPageIndex(dest[0])
      pageNumber = pageIdx + 1
    }
  } catch {
    // 忽略无法解析的 dest
  }

  const children: OutlineItem[] = []
  if (raw.items && raw.items.length > 0) {
    for (const child of raw.items as Array<{ title: string; dest: unknown; items: unknown[] }>) {
      children.push(await resolveOutlineItem(child))
    }
  }

  return { title: raw.title, dest: raw.dest, items: children, pageNumber }
}
```

在 `loadPdf()` 函数中，`renderer.init(pdfDocProxy)` 之后调用 `loadOutline()`：

```typescript
// 在 loadPdf() 中，renderer.init(pdfDocProxy) 之后：
await loadOutline()
```

在 template 中添加 PdfOutline 组件（在 `.reader-panel` div 内，toolbar 下方）：

```html
<PdfOutline
  :open="outlineOpen"
  :items="outlineItems"
  @close="outlineOpen = false"
  @navigate="renderer.scrollToPage"
/>
```

需要让 `.reader-panel` 变为 `position: relative` 以支持 PdfOutline 的 absolute 定位。在 CSS 中：

```css
.reader-panel {
  /* 已有 position: fixed; 加上 */
  /* 不需要改动，fixed 已经建立定位上下文 */
}
```

- [ ] **Step 4: 验证目录功能**

```bash
cd frontend
pnpm dev
# 打开 PDF 阅读器，点击工具栏目录按钮
# 确认：目录显示、点击跳转、折叠子项、窄屏覆盖
```

- [ ] **Step 5: 提交**

```bash
cd frontend
git add src/components/pdf-reader/PdfOutline.vue src/components/pdf-reader/PdfOutlineItem.vue src/components/PdfReaderPanel.vue
git commit -m "feat: 添加 PDF 目录侧栏，支持书签导航"
```

---

### Task 10: use-pdf-keyboard.ts — 键盘快捷键

**Files:**
- Create: `frontend/src/composables/use-pdf-keyboard.ts`
- Modify: `frontend/src/components/PdfReaderPanel.vue`

- [ ] **Step 1: 创建 use-pdf-keyboard.ts**

```typescript
// frontend/src/composables/use-pdf-keyboard.ts
import { onMounted, onBeforeUnmount, type Ref } from 'vue'

interface KeyboardOptions {
  active: Ref<boolean>
  currentPage: Ref<number>
  totalPages: Ref<number>
  onClose: () => void
  onScrollToPage: (page: number) => void
  onZoomIn: () => void
  onZoomOut: () => void
}

export function usePdfKeyboard(options: KeyboardOptions) {
  function handleKeydown(e: KeyboardEvent) {
    if (!options.active.value) return

    // 不要在 input/textarea 中拦截
    const tag = (e.target as HTMLElement)?.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA') return

    switch (true) {
      case e.key === 'ArrowUp' || e.key === 'k':
        e.preventDefault()
        options.onScrollToPage(options.currentPage.value - 1)
        break

      case e.key === 'ArrowDown' || e.key === 'j':
        e.preventDefault()
        options.onScrollToPage(options.currentPage.value + 1)
        break

      case e.key === '+' || e.key === '=':
        e.preventDefault()
        options.onZoomIn()
        break

      case e.key === '-':
        e.preventDefault()
        options.onZoomOut()
        break

      case e.key === 'Home' && e.ctrlKey:
        e.preventDefault()
        options.onScrollToPage(1)
        break

      case e.key === 'End' && e.ctrlKey:
        e.preventDefault()
        options.onScrollToPage(options.totalPages.value)
        break

      case e.key === 'Escape':
        e.preventDefault()
        options.onClose()
        break

      default:
        break
    }
  }

  onMounted(() => {
    document.addEventListener('keydown', handleKeydown)
  })

  onBeforeUnmount(() => {
    document.removeEventListener('keydown', handleKeydown)
  })
}
```

- [ ] **Step 2: 在 PdfReaderPanel.vue 中集成**

添加导入：

```typescript
import { usePdfKeyboard } from '../composables/use-pdf-keyboard'
```

在 `setup` 中调用：

```typescript
usePdfKeyboard({
  active: computed(() => props.visible),
  currentPage: renderer.currentPage,
  totalPages: renderer.totalPages,
  onClose: () => emit('close'),
  onScrollToPage: renderer.scrollToPage,
  onZoomIn: () => setScale(Math.min(3, scale.value + 0.25)),
  onZoomOut: () => setScale(Math.max(0.5, scale.value - 0.25)),
})
```

- [ ] **Step 3: 验证快捷键**

```bash
cd frontend
pnpm dev
# 打开 PDF 阅读器，测试：
# j/↓: 下一页, k/↑: 上一页
# +/-: 缩放
# Ctrl+Home/End: 首页/末页
# Escape: 关闭
```

- [ ] **Step 4: 提交**

```bash
cd frontend
git add src/composables/use-pdf-keyboard.ts src/components/PdfReaderPanel.vue
git commit -m "feat: 添加 PDF 阅读器键盘快捷键（j/k/+/-/Ctrl+Home/End/Esc）"
```

---

## 阶段 D: 引用高亮

### Task 11: UI store 更新 + 引用高亮

**Files:**
- Modify: `frontend/src/stores/ui.ts`
- Modify: `frontend/src/components/pdf-reader/PdfPage.vue`
- Modify: `frontend/src/components/PdfReaderPanel.vue`

- [ ] **Step 1: UI store 添加 readerHighlightText**

在 `frontend/src/stores/ui.ts` 中，`closeReader()` 函数之后添加：

```typescript
const readerHighlightText = ref<string | null>(null)

function openReader(paperId: string, page?: number, highlightText?: string) {
  readerPaperId.value = paperId
  readerTargetPage.value = page
  readerHighlightText.value = highlightText ?? null
  readerOpen.value = true
}

function closeReader() {
  readerOpen.value = false
  readerPaperId.value = null
  readerTargetPage.value = undefined
  readerHighlightText.value = null
}
```

更新 return 中的导出列表，添加 `readerHighlightText`。

- [ ] **Step 2: PdfReaderPanel 传递高亮文本给 PdfPage**

添加 `highlightText` prop 到 PdfReaderPanel：

```typescript
const props = defineProps<{
  visible: boolean
  paperId: string
  targetPage?: number
  highlightText?: string
  demoMode?: boolean
}>()
```

在 PdfPage 渲染处传递：

```html
<PdfPage
  v-if="renderer.pagesToRender.value.includes(pageNum)"
  :pdf-doc="pdfDocProxy"
  :page-number="pageNum"
  :scale="scale"
  :container-width="containerWidth"
  :highlight-text="pageNum === highlightTargetPage ? highlightText : undefined"
  @page-height="(h) => onPgeHeight(pageNum, h)"
/>
```

添加计算属性：

```typescript
const highlightTargetPage = computed(() => props.targetPage)
const highlightText = computed(() => props.highlightText)
```

- [ ] **Step 3: PdfPage.vue 添加引用高亮渲染**

在 PdfPage 的 props 中添加：

```typescript
const props = defineProps<{
  pdfDoc: PDFDocumentProxy
  pageNumber: number
  scale: number
  containerWidth: number
  highlightText?: string
}>()
```

在 `render()` 函数末尾（文本层渲染后）添加高亮逻辑：

```typescript
async function highlightOnPage() {
  if (!props.highlightText || !pageProxy || !containerRef.value) return

  const textContent = await pageProxy.getTextContent()
  const fullText = textContent.items
    .map((item) => ('str' in item ? item.str : ''))
    .join('')

  const searchStr = props.highlightText.trim()
  const idx = fullText.indexOf(searchStr)

  if (idx === -1) {
    // 没找到：边框闪烁
    containerRef.value.classList.add('pdf-page-flash')
    setTimeout(() => containerRef.value?.classList.remove('pdf-page-flash'), 2000)
    return
  }

  // 创建高亮覆盖层
  const overlay = document.createElement('div')
  overlay.className = 'pdf-highlight-overlay'
  overlay.style.position = 'absolute'
  overlay.style.top = '0'
  overlay.style.left = '0'
  overlay.style.right = '0'
  overlay.style.bottom = '0'
  overlay.style.pointerEvents = 'none'
  containerRef.value.appendChild(overlay)

  // 3 秒后淡出
  setTimeout(() => {
    overlay.classList.add('pdf-highlight-fadeout')
    setTimeout(() => overlay.remove(), 3000)
  }, 3000)
}
```

在 `render()` 函数中，文本层渲染完成后调用：

```typescript
// render() 函数末尾，await renderTextLayer(...) 之后：
if (props.highlightText) {
  await highlightOnPage()
}
```

添加高亮 CSS：

```css
.pdf-highlight-overlay {
  background: rgba(59, 130, 246, 0.15);
  animation: highlight-pulse 0.3s ease-out;
}

@keyframes highlight-pulse {
  from { background: rgba(59, 130, 246, 0.3); }
  to { background: rgba(59, 130, 246, 0.15); }
}

.pdf-highlight-fadeout {
  animation: highlight-fade 3s ease-out forwards;
}

@keyframes highlight-fade {
  from { opacity: 1; }
  to { opacity: 0; }
}

.pdf-page-flash {
  animation: page-flash-border 0.5s ease-out 3;
}

@keyframes page-flash-border {
  0%, 100% { box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08); }
  50% { box-shadow: 0 0 0 2px var(--color-accent); }
}
```

- [ ] **Step 4: 更新 ChatView.vue 传递 highlightText**

在 `ChatView.vue` 中，PdfReaderPanel 组件的调用处添加 `:highlight-text` prop：

```html
<PdfReaderPanel
  :visible="uiStore.readerOpen"
  :paper-id="uiStore.readerPaperId ?? ''"
  :target-page="uiStore.readerTargetPage"
  :highlight-text="uiStore.readerHighlightText ?? undefined"
  :demo-mode="demoActive"
  @close="uiStore.closeReader()"
/>
```

- [ ] **Step 5: 验证引用高亮**

```bash
cd frontend
pnpm dev
# 在 AI 对话中点击引用 [N]
# 确认：跳转到目标页，高亮文本出现，3 秒后淡出
# 测试不匹配的情况：边框闪烁
```

- [ ] **Step 6: 提交**

```bash
cd frontend
git add src/stores/ui.ts src/components/PdfReaderPanel.vue src/components/pdf-reader/PdfPage.vue src/views/ChatView.vue
git commit -m "feat: 添加引用高亮功能，点击引用跳转并高亮原文"
```

---

## 最终集成

### Task 12: WPS 构建验证 + 清理

**Files:**
- Review: `frontend/vite.config.ts`（确保 cmaps 被 Vite 自动复制）
- Review: 整体构建

- [ ] **Step 1: 验证 dev 完整功能**

```bash
cd frontend
pnpm dev
```

逐项验证：
1. 点击引用 → PDF 阅读器打开 → 跳转到目标页
2. 鼠标选中文本 → Ctrl+C 复制
3. 连续滚动 → 页码自动更新
4. 点击目录按钮 → 侧栏打开 → 点击条目跳转
5. j/k/+/-/Escape 快捷键
6. 浏览器宽度拉到 400px → 窄屏布局

- [ ] **Step 2: 验证 WPS 构建**

```bash
cd frontend
pnpm build
```

确认：
- 构建不报错
- `dist/` 目录中有 `wps-plugin/taskpane.html`
- `dist/` 中有 `cmaps/` 目录

- [ ] **Step 3: 清理旧 PdfReaderPanel 中不再需要的代码**

检查并移除：
- 旧的 `BUFFER` 常量
- 旧的 `canvasRefs` Map
- 旧的 `renderedSet` Set
- 旧的 `renderPage`、`renderVisiblePages` 函数
- 旧的 `renderedPages` computed

- [ ] **Step 4: 最终提交**

```bash
cd frontend
git add -A
git commit -m "chore: 清理旧 PdfReaderPanel 遗留代码，WPS 构建验证通过"
```

---

## Self-Review Checklist

- [x] Spec coverage: F1.1 (Task 1-3), F1.2 (Task 7), F1.3 (Task 4-6), F1.4 (Task 9), F1.5 (Task 10), F1.6 (Task 11), F1.7 (Task 9 CSS 响应式)
- [x] No placeholders: 所有代码完整，无 TBD/TODO
- [x] Type consistency: usePdfjs 返回 { lib, cMapOptions }，全文一致；OutlineItem 类型在 PdfOutline.vue 定义并导出
- [x] File structure: 4 个新组件 + 3 个新 composable，职责清晰
