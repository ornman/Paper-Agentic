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

  /* ── PDF 阅读面板 ── */
  const readerOpen = ref(false)
  const readerPaperId = ref<string | null>(null)
  const readerTargetPage = ref<number | undefined>(undefined)
  const readerHighlightText = ref<string | null>(null)

  function openReader(paperId: string, page?: number, highlightText?: string) {
    readerPaperId.value = paperId
    readerTargetPage.value = page
    readerHighlightText.value = highlightText ?? null
    readerOpen.value = true
  }

  function closeReader() {
    readerOpen.value = false
    readerPaperId.value = null
    readerTargetPage.value = undefined
    readerHighlightText.value = null
  }

  return {
    sidebarOpen,
    sidebarTab,
    openSidebar,
    closeSidebar,
    readerOpen,
    readerPaperId,
    readerTargetPage,
    readerHighlightText,
    openReader,
    closeReader,
  }
})
