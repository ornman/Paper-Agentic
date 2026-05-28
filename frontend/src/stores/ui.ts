import { defineStore } from 'pinia'
import { ref } from 'vue'

export type SidebarTab = 'history' | 'library'

export const useUiStore = defineStore('ui', () => {
  /** 侧栏抽屉是否打开 */
  const sidebarOpen = ref(false)

  /** 侧栏当前激活的 Tab */
  const sidebarTab = ref<SidebarTab>('history')

  function openSidebar(tab?: SidebarTab) {
    if (tab) sidebarTab.value = tab
    sidebarOpen.value = true
  }

  function closeSidebar() {
    sidebarOpen.value = false
  }

  return {
    sidebarOpen,
    sidebarTab,
    openSidebar,
    closeSidebar,
  }
})
