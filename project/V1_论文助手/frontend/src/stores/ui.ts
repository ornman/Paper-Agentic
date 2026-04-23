import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUiStore = defineStore('ui', () => {
  const historyDrawerOpen = ref(false)
  const libraryDrawerOpen = ref(false)

  function openHistoryDrawer() {
    historyDrawerOpen.value = true
    libraryDrawerOpen.value = false
  }

  function closeHistoryDrawer() {
    historyDrawerOpen.value = false
  }

  function openLibraryDrawer() {
    libraryDrawerOpen.value = true
    historyDrawerOpen.value = false
  }

  function closeLibraryDrawer() {
    libraryDrawerOpen.value = false
  }

  function closeAllDrawers() {
    historyDrawerOpen.value = false
    libraryDrawerOpen.value = false
  }

  return {
    historyDrawerOpen,
    libraryDrawerOpen,
    openHistoryDrawer,
    closeHistoryDrawer,
    openLibraryDrawer,
    closeLibraryDrawer,
    closeAllDrawers,
  }
})
