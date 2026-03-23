<script setup lang="ts">
import TabBar from './components/layout/TabBar.vue'
import TabContent from './components/layout/TabContent.vue'
</script>

<template>
  <div class="app-container">
    <TabBar />
    <TabContent />
  </div>
</template>

<style scoped>
.app-container {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
}
</style>
