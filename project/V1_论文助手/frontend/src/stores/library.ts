// 文献库状态管理
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  fetchPapers,
  deletePaper,
  startImport,
  createImportStream,
  type PaperItem,
  type ImportProgressEvent,
} from '../services/library-api'

export const useLibraryStore = defineStore('library', () => {
  const papers = ref<PaperItem[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const searchQuery = ref('')

  // 导入状态
  const importing = ref(false)
  const importFileName = ref('')
  const importStep = ref('')
  const importPercent = ref(0)
  const importError = ref<string | null>(null)

  const filteredPapers = computed(() => {
    if (!searchQuery.value.trim()) return papers.value
    const q = searchQuery.value.toLowerCase()
    return papers.value.filter(
      (p) =>
        p.title.toLowerCase().includes(q) ||
        p.authors.toLowerCase().includes(q),
    )
  })

  const paperCount = computed(() => papers.value.length)

  async function loadPapers() {
    loading.value = true
    error.value = null
    try {
      const result = await fetchPapers()
      papers.value = result.papers
    } catch (e: any) {
      error.value = e.message || '加载论文列表失败'
    } finally {
      loading.value = false
    }
  }

  async function removePaper(paperId: string) {
    try {
      await deletePaper(paperId)
      papers.value = papers.value.filter((p) => p.paper_id !== paperId)
    } catch (e: any) {
      error.value = e.message || '删除失败'
      throw e
    }
  }

  async function importFile(file: File) {
    importing.value = true
    importFileName.value = file.name
    importStep.value = '提交中...'
    importPercent.value = 0
    importError.value = null

    try {
      const result = await startImport(file)
      listenImportProgress(result.task_id)
    } catch (e: any) {
      importing.value = false
      importError.value = e.message || '导入失败'
    }
  }

  function listenImportProgress(taskId: string) {
    const es = createImportStream(taskId)

    es.onmessage = (event) => {
      try {
        const data: ImportProgressEvent = JSON.parse(event.data)

        if (data.status === 'completed') {
          importStep.value = '导入完成'
          importPercent.value = 100
          importing.value = false
          es.close()
          loadPapers()
        } else if (data.status === 'failed' || data.status === 'error') {
          importStep.value = '导入失败'
          importError.value = data.step || '未知错误'
          importing.value = false
          es.close()
        } else {
          importStep.value = data.step || '处理中...'
          importPercent.value = Math.min(importPercent.value + 15, 90)
        }
      } catch {
        // 忽略解析错误
      }
    }

    es.onerror = () => {
      es.close()
      importing.value = false
      if (importPercent.value < 100) {
        importError.value = '连接中断'
      }
    }
  }

  function clearImportError() {
    importError.value = null
  }

  return {
    papers,
    loading,
    error,
    searchQuery,
    filteredPapers,
    paperCount,
    importing,
    importFileName,
    importStep,
    importPercent,
    importError,
    loadPapers,
    removePaper,
    importFile,
    clearImportError,
  }
})
