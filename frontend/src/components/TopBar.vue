<template>
  <TopNavBar title="论文助手" @new-chat="emit('new-chat')" @open-history="emit('open-history')" />
</template>

<script setup lang="ts">
import TopNavBar from './TopNavBar.vue'

const emit = defineEmits<{
  (e: 'new-chat'): void
  (e: 'open-history'): void
}>()
</script>
