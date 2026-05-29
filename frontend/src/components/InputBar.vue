<template>
  <div class="input-bar-anchor">
    <div class="input-bar" :class="{ expanded }">
      <!-- 已选文献标签（带悬浮预览） -->
      <div
        v-if="selectedPaperCount > 0"
        class="paper-badge"
        @click="emit('toggle-papers')"
        @mouseenter="badgeHover = true"
        @mouseleave="badgeHover = false"
      >
        <span class="badge-icon" v-html="icons.doc" />
        <span>已引用 {{ selectedPaperCount }} 篇参考文献</span>
        <button class="badge-clear" type="button" @click.stop="emit('clear-papers')">×</button>

        <!-- 悬浮文献列表 -->
        <Transition name="badge-pop">
          <div v-if="badgeHover" class="badge-tooltip" @mouseenter="badgeHover = true" @mouseleave="badgeHover = false">
            <div class="badge-tooltip-title">已引用文献</div>
            <div v-for="name in selectedPaperNames" :key="name" class="badge-tooltip-item">
              <span class="badge-tooltip-dot" />
              {{ name }}
            </div>
          </div>
        </Transition>
      </div>

      <!-- 输入容器 -->
      <div class="input-container">
        <textarea
          ref="textareaEl"
          v-model="text"
          class="composer-textarea"
          :placeholder="placeholderText"
          rows="1"
          aria-label="输入消息"
          @keydown.enter.exact.prevent="handleSend"
          @input="autoResize"
        />
        <div class="input-actions">
          <button
            class="action-btn expand-btn"
            :class="{ active: expanded }"
            type="button"
            :title="expanded ? '收起' : '展开编辑'"
            @click="toggleExpand"
          >
            <span v-html="icons.expand" />
          </button>
          <button
            v-if="isBusy"
            class="action-btn stop-btn"
            type="button"
            title="停止生成"
            @click="emit('stop')"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor"><rect x="4" y="4" width="12" height="12" rx="2"/></svg>
          </button>
          <button
            v-else
            class="action-btn send-btn"
            type="button"
            :disabled="!text.trim()"
            @click="handleSend"
          >
            <span v-html="icons.send" />
          </button>
        </div>
      </div>

      <!-- 快捷操作栏 -->
      <div class="action-bar" :class="{ 'expanded-bar': expanded }">
        <div class="action-bar-left">
          <button class="action-chip" type="button" @click="emit('toggle-papers')">
            <span class="chip-icon" v-html="icons.search" />
            <span>引用文献</span>
          </button>
          <button class="action-chip" type="button" @click="triggerUpload">
            <span class="chip-icon" v-html="icons.docAdd" />
            <span>导入论文</span>
          </button>
          <button
            class="action-chip"
            :class="{ active: thinkingEnabled }"
            type="button"
            title="让 AI 展示推理过程，适合复杂分析"
            @click="emit('toggle-thinking')"
          >
            <span class="chip-icon" v-html="icons.lightbulb" />
            <span>深度思考</span>
          </button>
        </div>
        <Transition name="action-slide">
          <span
            v-if="expanded && selectedPaperCount > 0"
            class="meta-papers"
            @click="emit('toggle-papers')"
          >
            {{ selectedPaperCount }} 篇参考文献已引用
          </span>
        </Transition>
      </div>
    </div>
    <input ref="fileInput" type="file" accept=".pdf" hidden @change="handleFileChange" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import iconSearch from '../assets/icons/search-sparkle.svg?raw'
import iconDocAdd from '../assets/icons/document-add.svg?raw'
import iconLightbulb from '../assets/icons/lightbulb-filament.svg?raw'
import iconSend from '../assets/icons/lets-icons--send.svg?raw'
import iconExpand from '../assets/icons/expand.svg?raw'

const icons = {
  search: iconSearch,
  docAdd: iconDocAdd,
  lightbulb: iconLightbulb,
  send: iconSend,
  expand: iconExpand,
  doc: iconDocAdd,
}

const props = defineProps<{
  isBusy: boolean
  selectedPaperCount: number
  thinkingEnabled: boolean
  selectedPaperNames?: string[]
}>()

const emit = defineEmits<{
  (e: 'send', text: string): void
  (e: 'stop'): void
  (e: 'upload-pdf', file: File): void
  (e: 'toggle-papers'): void
  (e: 'clear-papers'): void
  (e: 'toggle-thinking'): void
}>()

const text = ref('')
const fileInput = ref<HTMLInputElement>()
const textareaEl = ref<HTMLTextAreaElement>()
const expanded = ref(false)
const badgeHover = ref(false)

const placeholderText = computed(() => {
  if (props.isBusy) return 'AI 正在回答中，发送新消息会中断当前回复'
  if (props.selectedPaperCount > 0) return `基于 ${props.selectedPaperCount} 篇参考文献回答...`
  return '输入你的问题...'
})

function toggleExpand() {
  expanded.value = !expanded.value
  if (expanded.value) {
    nextTick(() => {
      if (textareaEl.value) textareaEl.value.style.height = ''
      textareaEl.value?.focus()
    })
  } else {
    nextTick(() => {
      const el = textareaEl.value
      if (!el) return
      el.style.height = 'auto'
      el.style.height = Math.min(el.scrollHeight, 120) + 'px'
    })
  }
}

function handleSend() {
  const trimmed = text.value.trim()
  if (!trimmed) return
  emit('send', trimmed)
  text.value = ''
  expanded.value = false
  if (textareaEl.value) {
    textareaEl.value.style.height = 'auto'
  }
}

function triggerUpload() {
  fileInput.value?.click()
}

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) {
    emit('upload-pdf', file)
    target.value = ''
  }
}

function autoResize(event: Event) {
  if (expanded.value) return
  const el = event.target as HTMLTextAreaElement
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}
</script>

<style scoped>
.input-bar-anchor {
  max-width: 860px;
  margin: 0 auto;
  width: 100%;
  padding: 0 var(--space-4);
}

.input-bar {
  display: flex;
  flex-direction: column;
  background: var(--color-surface-card);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-lg);
  padding: var(--space-3) var(--space-4);
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--duration-fast) ease,
              border-color var(--duration-fast) ease,
              height 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.input-bar:focus-within {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px var(--color-accent-soft), var(--shadow-sm);
}

.input-bar.expanded {
  height: 55vh;
}

/* ── 文献标签 ── */
.paper-badge {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 4px 10px;
  margin-bottom: var(--space-2);
  font-size: 12px;
  color: var(--color-accent);
  background: var(--color-accent-soft);
  border-radius: var(--radius-full);
  cursor: pointer;
  flex-shrink: 0;
  align-self: flex-start;
}

.badge-icon {
  display: flex;
  width: 14px;
  height: 14px;
}

.badge-icon :deep(svg) {
  width: 100%;
  height: 100%;
}

.badge-clear {
  font-size: 14px;
  line-height: 1;
  color: var(--color-accent);
  cursor: pointer;
}

/* ── 文献悬浮提示 ── */
.badge-tooltip {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 0;
  min-width: 200px;
  max-width: 300px;
  padding: var(--space-3);
  background: color-mix(in srgb, var(--color-surface-card) 92%, transparent);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-md);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  z-index: 100;
}

.badge-tooltip-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-muted);
  margin-bottom: var(--space-2);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.badge-tooltip-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 12px;
  color: var(--color-text-primary);
  padding: 3px 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.badge-tooltip-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--color-accent);
  flex-shrink: 0;
}

.badge-pop-enter-active {
  transition: opacity 0.15s var(--ease-out-expo), transform 0.15s var(--ease-out-expo);
}

.badge-pop-leave-active {
  transition: opacity 0.1s ease, transform 0.1s ease;
}

.badge-pop-enter-from {
  opacity: 0;
  transform: translateY(4px) scale(0.96);
}

.badge-pop-leave-to {
  opacity: 0;
  transform: translateY(2px) scale(0.97);
}

/* ── 输入容器 ── */
.input-container {
  display: flex;
  align-items: flex-end;
  gap: var(--space-2);
  flex: 1;
  min-height: 0;
}

.input-bar.expanded .input-container {
  align-items: stretch;
}

.input-bar.expanded .input-actions {
  align-self: flex-end;
}

.composer-textarea {
  flex: 1;
  padding: 8px 0;
  border: none;
  background: transparent;
  font-size: var(--font-size-base);
  line-height: 1.6;
  resize: none;
  outline: none;
  color: var(--color-text-primary);
  max-height: 120px;
}

.input-bar.expanded .composer-textarea {
  max-height: none;
  padding: 8px 0;
}

.composer-textarea::placeholder {
  color: var(--color-text-muted);
}

/* ── 操作按钮组 ── */
.input-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.action-btn {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-full);
  transition: background var(--duration-fast) ease,
              opacity var(--duration-fast) ease,
              transform var(--duration-fast) ease;
}

.action-btn :deep(svg) {
  width: 20px;
  height: 20px;
}

/* 展开按钮：始终可见，默认低调 */
.expand-btn {
  width: 26px;
  height: 26px;
  background: transparent;
  color: var(--color-text-muted);
  opacity: 0.4;
}

.expand-btn :deep(svg) {
  width: 13px;
  height: 13px;
}

.expand-btn:hover {
  background: var(--color-surface-muted);
  color: var(--color-accent);
  opacity: 1;
}

.expand-btn.active {
  background: var(--color-accent-soft);
  color: var(--color-accent);
  opacity: 1;
}

/* 发送按钮 */
.send-btn {
  background: linear-gradient(135deg, #3bd5ff, #0094f0);
  color: #fff;
  box-shadow: 0 2px 8px rgba(0, 148, 240, 0.25);
}

.send-btn :deep(svg) {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.send-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
  box-shadow: none;
}

.send-btn:not(:disabled):hover {
  opacity: 0.9;
  transform: scale(1.05);
}

.send-btn:not(:disabled):active {
  transform: scale(0.95);
}

/* 停止按钮 */
.stop-btn {
  background: var(--color-error, #c53030);
  color: #fff;
}

.stop-btn:hover {
  opacity: 0.9;
  transform: scale(1.05);
}

/* ── 快捷操作栏 ── */
.action-bar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid var(--color-border-subtle);
  flex-shrink: 0;
}

.expanded-bar {
  justify-content: space-between;
}

.action-bar-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.meta-papers {
  font-size: 11px;
  color: var(--color-accent);
  background: var(--color-accent-soft);
  padding: 3px 10px;
  border-radius: var(--radius-full);
  cursor: pointer;
}

.action-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 14px;
  font-size: 12px;
  color: var(--color-text-secondary);
  background: var(--color-surface-muted);
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: background var(--duration-fast) ease,
              color var(--duration-fast) ease,
              transform var(--duration-fast) ease;
}

.action-chip:hover {
  background: var(--color-accent-soft);
  color: var(--color-accent);
  transform: translateY(-1px);
}

.action-chip:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}

.action-chip.active {
  background: var(--color-accent-soft);
  color: var(--color-accent);
}

.chip-icon {
  display: flex;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.chip-icon :deep(svg) {
  width: 100%;
  height: 100%;
}

/* ── 动画 ── */
.action-slide-enter-active {
  transition: opacity var(--duration-normal) var(--ease-out-expo),
              transform var(--duration-normal) var(--ease-out-expo);
}

.action-slide-leave-active {
  transition: opacity var(--duration-fast) var(--ease-in-out),
              transform var(--duration-fast) var(--ease-in-out);
}

.action-slide-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.action-slide-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* ── WPS 窄屏适配 ── */
@media (max-width: 420px) {
  .input-bar-anchor {
    padding: 0 var(--space-2);
  }

  .input-bar {
    padding: var(--space-2) var(--space-3);
  }

  .action-bar {
    flex-wrap: wrap;
    gap: var(--space-1);
  }

  .action-chip {
    padding: 4px 10px;
    font-size: 11px;
  }

  .input-actions {
    gap: 2px;
  }

  .action-btn {
    width: 30px;
    height: 30px;
  }

  .action-btn :deep(svg) {
    width: 16px;
    height: 16px;
  }

  .badge-tooltip {
    min-width: 160px;
    max-width: 240px;
  }
}
</style>
