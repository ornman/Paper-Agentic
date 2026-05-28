<template>
  <header class="top-nav">
    <div class="top-left">
      <button class="icon-button" type="button" aria-label="菜单" @click="emit('open-history')">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <line x1="3" y1="6" x2="17" y2="6"></line>
          <line x1="3" y1="10" x2="17" y2="10"></line>
          <line x1="3" y1="14" x2="17" y2="14"></line>
        </svg>
      </button>
      <span class="nav-logo clickable" v-html="logoSvg" @click="emit('new-chat')" />
      <h1 class="page-title clickable" @click="emit('new-chat')">{{ title }}</h1>
    </div>
    <div class="top-right">
      <!-- 新建对话 -->
      <button class="icon-button" type="button" aria-label="新建对话" @click="emit('new-chat')">
        <span class="icon-svg" v-html="iconChatAdd" />
      </button>
      <!-- 设置按钮 -->
      <router-link to="/settings" class="icon-button icon-button--settings" aria-label="设置">
        <span class="icon-svg" v-html="iconSettings" />
      </router-link>
    </div>
  </header>
</template>

<script setup lang="ts">
import logoSvg from '../assets/icons/ai-science-spark.svg?raw'
import iconChatAdd from '../assets/icons/chat-add.svg?raw'
import iconSettings from '../assets/icons/settings.svg?raw'

const emit = defineEmits<{
  (event: 'open-history'): void
  (event: 'new-chat'): void
}>()

defineProps<{
  title: string
}>()
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

.top-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.nav-logo {
  display: flex;
  width: 26px;
  height: 26px;
  flex-shrink: 0;
}

.nav-logo :deep(svg) {
  width: 100%;
  height: 100%;
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

.clickable {
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: opacity 0.15s ease;
}

.clickable:hover {
  opacity: 0.7;
}

.page-title {
  color: var(--color-text-primary);
  font-size: 18px;
  font-weight: 600;
  text-align: center;
  line-height: 1;
}

.icon-button--settings {
  color: var(--color-text-secondary);
}

.icon-button--settings:hover {
  color: var(--color-text-primary);
}

.icon-svg {
  display: inline-flex;
  width: 20px;
  height: 20px;
  color: currentColor;
}

.icon-svg :deep(svg) {
  width: 100%;
  height: 100%;
}
</style>
