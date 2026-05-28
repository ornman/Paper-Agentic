<template>
  <div class="empty-state">
    <h1 class="empty-title">今天有什么可以帮到你？</h1>
    <p class="empty-hint">输入你的问题，开始与论文对话</p>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  min-height: 60vh;
  text-align: center;
  user-select: none;
}

.empty-title {
  font-size: 26px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 8px;
  letter-spacing: -0.3px;
}

.empty-hint {
  font-size: 14px;
  color: var(--color-text-muted);
}
</style>
