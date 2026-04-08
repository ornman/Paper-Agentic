import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUiStore = defineStore('ui', () => {
  // UI store 只保存最基础的界面状态。
  // Task 3 先把跨组件共享的开关与提示消息固定下来，避免组件里继续散落局部状态。
  const historyDrawerOpen = ref(false)
  const sidebarExpanded = ref(true)
  const toastMessage = ref<string | null>(null)

  /**
   * 打开历史抽屉。
   */
  function openHistoryDrawer() {
    historyDrawerOpen.value = true
  }

  /**
   * 关闭历史抽屉。
   */
  function closeHistoryDrawer() {
    historyDrawerOpen.value = false
  }

  /**
   * 切换侧边栏展开状态。
   * 这里只保留最小翻转动作，具体动画和布局联动放到后续任务。
   */
  function toggleSidebarExpanded() {
    sidebarExpanded.value = !sidebarExpanded.value
  }

  /**
   * 显示一条 toast 文案。
   */
  function showToast(message: string) {
    toastMessage.value = message
  }

  /**
   * 清空 toast。
   */
  function clearToast() {
    toastMessage.value = null
  }

  return {
    historyDrawerOpen,
    sidebarExpanded,
    toastMessage,
    openHistoryDrawer,
    closeHistoryDrawer,
    toggleSidebarExpanded,
    showToast,
    clearToast,
  }
})
