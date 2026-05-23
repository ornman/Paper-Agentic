<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    title?: string
  }>(),
  {
    title: '新对话',
  },
)

const emit = defineEmits<{
  (event: 'open-history'): void
  (event: 'new-chat'): void
}>()
</script>

<template>
  <header class="top-nav" data-testid="top-nav">
    <button class="icon-button" type="button" aria-label="打开侧边导航" @click="emit('open-history')">
      <span class="hamburger-line" />
      <span class="hamburger-line" />
      <span class="hamburger-line" />
    </button>

    <h1 class="page-title">{{ props.title }}</h1>

    <button class="icon-button icon-button-right" type="button" aria-label="新建对话" @click="emit('new-chat')">
      <span class="new-chat-icon">
        <span class="new-chat-tail" />
        <span class="new-chat-plus">＋</span>
      </span>
    </button>
  </header>
</template>

<style scoped>
.top-nav {
  display: grid;
  grid-template-columns: 44px 1fr 44px;
  align-items: center;
  min-height: 52px;
  padding: 6px 10px 2px;
  background: transparent;
}

.icon-button {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 999px;
  background: transparent;
  cursor: pointer;
}

.page-title {
  color: var(--color-text-primary);
  font-size: 20px;
  line-height: 1;
  font-weight: 600;
  text-align: center;
}

.hamburger-line {
  display: block;
  width: 20px;
  height: 2px;
  border-radius: 999px;
  background: var(--color-text-primary);
}

.icon-button {
  gap: 5px;
  flex-direction: column;
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
