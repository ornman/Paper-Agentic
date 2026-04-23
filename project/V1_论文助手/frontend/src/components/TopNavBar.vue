<template>
  <header class="top-nav">
    <button class="icon-button" type="button" aria-label="打开菜单" @click="emit('open-history')">
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <line x1="3" y1="6" x2="17" y2="6"></line>
        <line x1="3" y1="10" x2="17" y2="10"></line>
        <line x1="3" y1="14" x2="17" y2="14"></line>
      </svg>
    </button>
    <h1 class="page-title">{{ title }}</h1>
    <div class="top-right">
      <!-- 新建对话 -->
      <button class="icon-button" type="button" aria-label="新建对话" @click="emit('new-chat')">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="16"></line>
          <line x1="8" y1="12" x2="16" y2="12"></line>
        </svg>
      </button>
      <!-- 设置按钮 -->
      <button class="icon-button" type="button" aria-label="设置" @click="showSettings = !showSettings">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"></circle>
          <path d="M12 1v6m0 6v6m0-6h6"></path>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
        </svg>
      </button>
    </div>
  </header>

  <!-- 设置弹窗 -->
  <Teleport to="body">
    <div v-if="showSettings" class="settings-overlay" @click="showSettings = false">
      <div class="settings-modal" @click.stop>
        <div class="settings-header">
          <h2>设置</h2>
          <button class="close-icon-btn" @click="showSettings = false">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="settings-body">
          <div class="setting-group">
            <h3>显示</h3>
            <div class="setting-item">
              <label class="setting-label">字体大小</label>
              <div class="font-control">
                <input type="range" v-model.number="fontSize" min="12" max="24" step="1" class="font-slider">
                <span class="font-value">{{ fontSize }}px</span>
              </div>
            </div>
          </div>
        </div>
        <div class="settings-footer">
          <button class="btn-primary" @click="showSettings = false">完成</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'

const emit = defineEmits<{
  (event: 'open-history'): void
  (event: 'new-chat'): void
}>()

defineProps<{
  title: string
}>()

const fontSize = ref(16)
const showSettings = ref(false)

onMounted(() => {
  const saved = localStorage.getItem('fontSize')
  if (saved) fontSize.value = parseInt(saved)
  applyFontSize()
})

watch(fontSize, (newSize) => {
  localStorage.setItem('fontSize', String(newSize))
  applyFontSize()
})

function applyFontSize() {
  document.documentElement.style.setProperty('--font-size-base', `${fontSize.value}px`)
}
</script>

<style scoped>
/* ─── 顶部导航栏 ─── */
.top-nav {
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  background: var(--color-surface-base);
}

.icon-button {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--radius-full);
  background: transparent;
  color: var(--color-text-primary);
  cursor: pointer;
  transition: background 0.15s ease;
}

.icon-button:hover {
  background: var(--color-surface-muted);
}

.page-title {
  color: var(--color-text-primary);
  font-size: 18px;
  font-weight: 600;
  text-align: center;
  line-height: 1;
}

.top-right {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

/* ─── 设置弹窗 ─── */
.settings-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-4);
  background: rgba(0, 0, 0, 0.4);
  animation: fadeIn 0.15s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.settings-modal {
  width: 100%;
  max-width: 400px;
  background: var(--color-surface-base);
  border-radius: var(--radius-lg);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
  animation: slideUp 0.2s ease;
  display: flex;
  flex-direction: column;
  max-height: 80vh;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.settings-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--color-border-subtle);
}

.settings-header h2 {
  font-size: var(--font-size-title);
  font-weight: 600;
  color: var(--color-text-primary);
}

.close-icon-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.15s ease;
}

.close-icon-btn:hover {
  background: var(--color-surface-muted);
  color: var(--color-text-primary);
}

.settings-body {
  padding: var(--space-4) var(--space-5);
  overflow-y: auto;
}

.setting-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.setting-group h3 {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.setting-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.setting-label {
  font-size: var(--font-size-body);
  color: var(--color-text-primary);
  font-weight: 500;
}

.font-control {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.font-slider {
  flex: 1;
  height: 6px;
  -webkit-appearance: none;
  appearance: none;
  background: var(--color-border-subtle);
  border-radius: var(--radius-full);
  outline: none;
  cursor: pointer;
  margin: 8px 0;
}

.font-slider::-webkit-slider-runnable-track {
  height: 6px;
  border-radius: 3px;
  background: var(--color-border-subtle);
}

.font-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--color-accent);
  cursor: pointer;
  margin-top: -7px;
}

.font-slider::-moz-range-track {
  height: 6px;
  border-radius: 3px;
  background: var(--color-border-subtle);
}

.font-slider::-moz-range-thumb {
  width: 20px;
  height: 20px;
  border: none;
  border-radius: 50%;
  background: var(--color-accent);
  cursor: pointer;
}

.font-value {
  min-width: 42px;
  text-align: right;
  font-size: 13px;
  color: var(--color-text-secondary);
  font-variant-numeric: tabular-nums;
}

.settings-footer {
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--color-border-subtle);
  display: flex;
  justify-content: flex-end;
}

.btn-primary {
  padding: var(--space-2) var(--space-5);
  border: none;
  border-radius: var(--radius-full);
  background: var(--color-accent);
  color: #ffffff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.btn-primary:hover {
  opacity: 0.85;
}
</style>
