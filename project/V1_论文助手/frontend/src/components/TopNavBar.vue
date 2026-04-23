<script setup lang="ts">
const emit = defineEmits<{
  (event: 'open-history'): void
  (event: 'new-chat'): void
}>()
</script>

<template>
  <header class="top-nav">
    <button class="icon-button" type="button" aria-label="打开菜单" @click="emit('open-history')">
      <span class="hamburger-line" />
      <span class="hamburger-line" />
      <span class="hamburger-line" />
    </button>
    <h1 class="page-title">论文助手</h1>
    <button class="icon-button" type="button" aria-label="新建对话" @click="emit('new-chat')">
      <span class="new-chat-icon">
        <span class="new-chat-tail" />
        <span class="new-chat-plus">+</span>
      </span>
    </button>
  </header>
</template>

<style scoped>
.top-nav {
  display: grid;
  grid-template-columns: 44px 1fr 44px;
  align-items: center;
  min-height: 48px;
  padding: var(--space-1) var(--space-1) var(--space-2);
  background: transparent;
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
  cursor: pointer;
  gap: 5px;
  flex-direction: column;
  transition: background 0.15s ease;
}

.icon-button:hover {
  background: var(--color-border-subtle);
}

.page-title {
  color: var(--color-text-primary);
  font-size: var(--font-size-title);
  font-weight: 600;
  text-align: center;
  line-height: 1;
}

.hamburger-line {
  display: block;
  width: 20px;
  height: 2px;
  border-radius: var(--radius-full);
  background: var(--color-text-primary);
}

.new-chat-icon {
  position: relative;
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--color-text-primary);
  border-radius: 50%;
}

.new-chat-tail {
  position: absolute;
  left: 2px;
  bottom: -1px;
  width: 11px;
  height: 10px;
  border-left: 2px solid var(--color-text-primary);
  border-bottom: 2px solid var(--color-text-primary);
  border-radius: 0 0 0 10px;
  background: transparent;
}

.new-chat-plus {
  position: relative;
  z-index: 1;
  font-size: 15px;
  line-height: 1;
  font-weight: 600;
}
</style>
