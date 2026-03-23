<script setup lang="ts">
import { useMockStore } from '../../stores/mockStore'
import IngestPage from '../ingest/IngestPage.vue'
import ChatPage from '../chat/ChatPage.vue'
import SettingsPage from '../settings/SettingsPage.vue'

const store = useMockStore()
</script>

<template>
  <div class="tab-content">
    <IngestPage v-if="store.activeTab === 'ingest'" />
    <ChatPage v-else-if="store.activeTab === 'chat'" />
    <SettingsPage v-else-if="store.activeTab === 'settings'" />
  </div>
</template>

<style scoped>
.tab-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
</style>
