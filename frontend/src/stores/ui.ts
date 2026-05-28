import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUiStore = defineStore('ui', () => {
  /** 模型选择器面板是否展开 */
  const modelPanelOpen = ref(false)

  function toggleModelPanel() {
    modelPanelOpen.value = !modelPanelOpen.value
  }

  function closeModelPanel() {
    modelPanelOpen.value = false
  }

  return {
    modelPanelOpen,
    toggleModelPanel,
    closeModelPanel,
  }
})
