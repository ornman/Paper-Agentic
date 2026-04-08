<script setup lang="ts">
</script>

<template>
  <section class="empty-state" aria-label="论文创作空状态">
    <h1 class="hero-title">今天有什么可以帮到你？</h1>
  </section>
</template>

<style scoped>
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100%;
  padding: 0 18px;
  text-align: center;
}

.hero-title {
  color: var(--color-text-primary);
  font-size: clamp(30px, 5vw, 36px);
  line-height: 1.2;
  font-weight: 500;
  font-family: var(--font-family-base);
  letter-spacing: 0;
  white-space: nowrap;
}
</style>
