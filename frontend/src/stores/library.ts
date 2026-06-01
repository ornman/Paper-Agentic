// 文献库状态管理
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  fetchPapers,
  fetchTrashedPapers,
  deletePaper,
  restorePaper,
  permanentDeletePaper,
  startImport,
  fetchImportStatus,
} from '../services/library-api'
import type { PaperItem, ImportProgressEvent, ImportStatus } from '../types/paper'
import { ApiClientError } from '../services/api-client'
import { useLogger } from '../composables/logger'

const log = useLogger('api')

const STEP_LABELS: Record<string, string> = {
  starting: '正在准备导入...',
  queued: '等待处理...',
  transforming: '正在读取论文内容...',
  cleaning: '正在整理文本内容...',
  vlm_enriching: '正在识别图表和公式...',
  chunking: '正在分析论文结构...',
  embedding: '正在建立智能索引...',
  indexing: '即将完成，准备就绪...',
  running: '处理中...',
  done: '完成',
}

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

function isImportTerminalStatus(status: string) {
  return status === 'completed' || status === 'failed' || status === 'error'
}

export interface ImportQueueItem {
  fileName: string
  file?: File
  taskId?: string
  status: 'pending' | 'importing' | 'completed' | 'failed'
  percent: number
  step: string
  error?: string
}

const STORAGE_KEY = 'paper-agentic-import-queue'

function persistQueue(items: ImportQueueItem[]) {
  const serializable = items.map(({ fileName, taskId, status, percent, step, error }) => ({
    fileName, taskId, status, percent, step, error,
  }))
  localStorage.setItem(STORAGE_KEY, JSON.stringify(serializable))
}

function restoreQueue(): ImportQueueItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    return JSON.parse(raw)
  } catch {
    return []
  }
}

export const useLibraryStore = defineStore('library', () => {
  const papers = ref<PaperItem[]>([])
  const trashedPapers = ref<PaperItem[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const selectedPaperIds = ref<string[]>([])

  // 统一导入队列（单文件和批量共用）
  const importQueue = ref<ImportQueueItem[]>(restoreQueue())
  const importError = ref<string | null>(null)
  let lastProgressSignature = ''

  const selectedPaperCount = computed(() => selectedPaperIds.value.length)
  const paperCount = computed(() => papers.value.length)
  const isImporting = computed(() =>
    importQueue.value.some((item) => item.status === 'importing' || item.status === 'pending'),
  )

  async function loadPapers() {
    loading.value = true
    error.value = null
    try {
      const result = await fetchPapers()
      papers.value = result.papers
      log.info('加载论文列表成功', { count: result.papers.length })
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : '加载论文列表失败'
      log.error('加载论文列表失败', err)
    } finally {
      loading.value = false
    }
  }

  // 恢复刷新前进行中的导入任务
  async function resumeImports() {
    importQueue.value = importQueue.value.filter(
      (item) => item.taskId || item.file,
    )

    const active = importQueue.value.filter(
      (item) => item.status === 'importing' || item.status === 'pending',
    )
    if (active.length === 0) {
      importQueue.value = []
      localStorage.removeItem(STORAGE_KEY)
      return
    }

    for (const item of active) {
      const idx = importQueue.value.indexOf(item)
      if (idx === -1) continue
      if (item.taskId) {
        try {
          await monitorImportStatus(item.taskId, idx)
        } catch {
          item.status = 'failed'
          item.step = '导入失败（刷新后恢复）'
        }
      } else if (item.file) {
        try {
          const result = await startImport(item.file)
          item.taskId = result.task_id
          item.status = 'importing'
          item.percent = 8
          item.step = '任务已创建，等待处理'
          await monitorImportStatus(result.task_id, idx)
        } catch {
          item.status = 'failed'
          item.step = '导入失败'
        }
      }
    }
    persistQueue(importQueue.value)
    void loadPapers()
  }

  async function removePaper(paperId: string) {
    error.value = null
    log.info('开始删除论文', { paperId })

    try {
      await deletePaper(paperId)
      papers.value = papers.value.filter((paper) => paper.paper_id !== paperId)
      selectedPaperIds.value = selectedPaperIds.value.filter((id) => id !== paperId)
      log.info('删除论文成功', { paperId })
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : '删除失败'
      log.error('删除论文失败', err, { paperId })
      throw err
    }
  }

  async function loadTrashedPapers() {
    try {
      trashedPapers.value = await fetchTrashedPapers()
      log.info('加载回收站列表成功', { count: trashedPapers.value.length })
    } catch (err: unknown) {
      log.error('加载回收站列表失败', err)
    }
  }

  async function restorePaperFromTrash(paperId: string) {
    try {
      await restorePaper(paperId)
      trashedPapers.value = trashedPapers.value.filter((p) => p.paper_id !== paperId)
      await loadPapers()
      log.info('恢复论文成功', { paperId })
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : '恢复失败'
      log.error('恢复论文失败', err, { paperId })
      throw err
    }
  }

  async function permanentDeleteFromTrash(paperId: string) {
    try {
      await permanentDeletePaper(paperId)
      trashedPapers.value = trashedPapers.value.filter((p) => p.paper_id !== paperId)
      log.info('永久删除论文成功', { paperId })
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : '永久删除失败'
      log.error('永久删除论文失败', err, { paperId })
      throw err
    }
  }

  function setSelectedPaperIds(nextPaperIds: string[]) {
    selectedPaperIds.value = [...new Set(nextPaperIds)]
  }

  function togglePaperSelection(paperId: string) {
    if (selectedPaperIds.value.includes(paperId)) {
      selectedPaperIds.value = selectedPaperIds.value.filter((id) => id !== paperId)
      return
    }

    selectedPaperIds.value = [...selectedPaperIds.value, paperId]
  }

  function clearSelectedPapers() {
    selectedPaperIds.value = []
  }

  function setImportError(message: string | null) {
    importError.value = message
  }

  function applyImportProgress(progress: ImportProgressEvent, queueIdx: number) {
    if (queueIdx >= importQueue.value.length) return

    const nextSignature = [
      progress.status,
      progress.step ?? '',
      progress.paper_id ?? '',
      progress.error_msg ?? '',
      progress.file_name ?? '',
      typeof progress.percent === 'number' ? String(progress.percent) : '',
    ].join('|')

    if (nextSignature === lastProgressSignature) return
    lastProgressSignature = nextSignature

    const item = importQueue.value[queueIdx]
    const stepText = progress.error_msg || STEP_LABELS[progress.step ?? ''] || progress.step || '处理中...'
    const percent = typeof progress.percent === 'number'
      ? progress.percent
      : Math.min(item.percent + 12, 95)

    item.step = stepText
    item.percent = percent

    if (progress.status === 'completed') {
      item.status = 'completed'
      item.step = '已完成'
      item.percent = 100
      // 延迟 2 秒后自动移除已完成的队列项（用 fileName 匹配避免索引偏移）
      const fileName = item.fileName
      window.setTimeout(() => {
        const idx = importQueue.value.findIndex((q) => q.fileName === fileName && q.status === 'completed')
        if (idx !== -1) {
          importQueue.value.splice(idx, 1)
          persistQueue(importQueue.value)
        }
      }, 2000)
      log.info('导入完成', { paperId: progress.paper_id })
      void loadPapers()
      return
    }

    if (progress.status === 'failed' || progress.status === 'error') {
      const errMsg = progress.error_msg || progress.step || '遇到了意外问题，请稍后重试'
      item.status = 'failed'
      item.step = '导入失败'
      item.percent = 100
      item.error = errMsg
      log.warn('导入失败', { paperId: progress.paper_id, step: progress.step, error: progress.error_msg })
    }
  }

  function applyImportStatus(status: ImportStatus, queueIdx: number) {
    applyImportProgress({
      status: status.status,
      step: status.current_step,
      paper_id: status.paper_id,
      error_msg: status.error_msg,
      file_name: status.file_name,
      percent: status.percent,
    }, queueIdx)
  }

  async function monitorImportStatus(taskId: string, queueIdx: number, maxConsecutiveFailures = 30) {
    let consecutiveFailures = 0

    while (true) {
      try {
        const status = await fetchImportStatus(taskId)
        consecutiveFailures = 0
        log.info('轮询导入状态', { taskId, status: status.status, step: status.current_step, percent: status.percent })
        applyImportStatus(status, queueIdx)

        if (isImportTerminalStatus(status.status)) return
      } catch (err: unknown) {
        if (err instanceof ApiClientError && err.statusCode === 400) {
          if (queueIdx < importQueue.value.length) {
            importQueue.value[queueIdx].status = 'failed'
            importQueue.value[queueIdx].step = '导入失败'
            importQueue.value[queueIdx].error = err.message || '导入失败'
          }
          log.warn('导入任务返回业务错误', { taskId, message: err.message })
          return
        }

        consecutiveFailures += 1
        log.warn('轮询导入状态失败', {
          taskId,
          consecutiveFailures,
          message: err instanceof Error ? err.message : String(err),
        })
        if (consecutiveFailures >= maxConsecutiveFailures) {
          const msg = `导入似乎中断了，请尝试重新上传`
          if (queueIdx < importQueue.value.length) {
            importQueue.value[queueIdx].status = 'failed'
            importQueue.value[queueIdx].step = '导入中断'
            importQueue.value[queueIdx].error = msg
          }
          return
        }
      }

      await wait(1000)
    }
  }

  async function importFiles(files: File[]) {
    if (files.length === 0) return

    importError.value = null
    error.value = null

    importQueue.value = files.map((f) => ({
      fileName: f.name,
      file: f,
      status: 'pending' as const,
      percent: 0,
      step: '等待中',
    }))

    const dupNames: string[] = []

    for (let i = 0; i < files.length; i++) {
      const item = importQueue.value[i]
      if (item.status === 'completed') continue
      item.status = 'importing'
      item.percent = 2
      item.step = '提交中...'
      lastProgressSignature = ''

      try {
        const result = await startImport(files[i])
        item.taskId = result.task_id
        item.percent = 8
        item.step = '任务已创建，等待处理'
        persistQueue(importQueue.value)
        log.info('导入任务已创建', { taskId: result.task_id, fileName: files[i].name })
        await monitorImportStatus(result.task_id, i)
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : '导入失败'
        // 重复导入：直接从队列移除，记入跳过
        if (msg.includes('已导入过')) {
          dupNames.push(item.fileName)
          importQueue.value.splice(i, 1)
          i-- // splice 后索引偏移
          continue
        }
        item.status = 'failed'
        item.error = msg
        item.step = '导入失败'
        log.error('批量导入中单文件失败', err, { name: files[i].name })
      }

      persistQueue(importQueue.value)
    }

    // 先加载论文列表，避免队列清空后出现空白闪烁
    await loadPapers()

    // 再清理已完成的队列项，只保留失败的
    importQueue.value = importQueue.value.filter((item) => item.status === 'failed')

    if (dupNames.length > 0) {
      importError.value = `${dupNames.length} 篇论文已导入过，已跳过：${dupNames.join('、')}`
    }

    persistQueue(importQueue.value)
  }

  function clearImportError() {
    importError.value = null
  }

  function clearImportQueue() {
    importQueue.value = []
  }

  function removeQueueItem(index: number) {
    importQueue.value.splice(index, 1)
    persistQueue(importQueue.value)
  }

  async function retryQueueItem(index: number) {
    const item = importQueue.value[index]
    if (!item || !item.file) return

    item.status = 'importing'
    item.percent = 2
    item.step = '提交中...'
    item.error = undefined
    lastProgressSignature = ''

    try {
      const result = await startImport(item.file)
      item.percent = 8
      item.step = '任务已创建，等待处理'
      log.info('重试导入', { taskId: result.task_id, fileName: item.fileName })
      await monitorImportStatus(result.task_id, index)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '导入失败'
      item.status = 'failed'
      item.error = msg
      item.step = '导入失败'
      log.error('重试导入失败', err, { name: item.fileName })
    }
  }

  return {
    papers,
    trashedPapers,
    loading,
    error,
    selectedPaperIds,
    selectedPaperCount,
    paperCount,
    isImporting,
    importError,
    importQueue,
    loadPapers,
    resumeImports,
    removePaper,
    loadTrashedPapers,
    restorePaperFromTrash,
    permanentDeleteFromTrash,
    setSelectedPaperIds,
    togglePaperSelection,
    clearSelectedPapers,
    importFiles,
    monitorImportStatus,
    clearImportError,
    setImportError,
    clearImportQueue,
    removeQueueItem,
    retryQueueItem,
  }
})
