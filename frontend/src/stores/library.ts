// 文献库状态管理
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  fetchPapers,
  deletePaper,
  startImport,
  fetchImportStatus,
  type PaperItem,
  type ImportProgressEvent,
  type ImportStatus,
} from '../services/library-api'
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
  status: 'pending' | 'importing' | 'completed' | 'failed'
  percent: number
  step: string
  error?: string
}

export const useLibraryStore = defineStore('library', () => {
  const papers = ref<PaperItem[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const selectedPaperIds = ref<string[]>([])

  // 单文件导入状态（InputBar 快捷上传）
  const importing = ref(false)
  const importFileName = ref('')
  const importStep = ref('')
  const importPercent = ref(0)
  const importError = ref<string | null>(null)

  // 批量导入队列
  const importQueue = ref<ImportQueueItem[]>([])
  let lastProgressSignature = ''

  const selectedPaperCount = computed(() => selectedPaperIds.value.length)
  const paperCount = computed(() => papers.value.length)

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

  function applyImportProgress(progress: ImportProgressEvent, queueIdx?: number) {
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

    const stepText = progress.error_msg || STEP_LABELS[progress.step ?? ''] || progress.step || '处理中...'
    const percent = typeof progress.percent === 'number'
      ? progress.percent
      : Math.min(importPercent.value + 12, 95)

    // 更新单文件全局状态
    if (progress.file_name) importFileName.value = progress.file_name
    importStep.value = stepText
    importPercent.value = percent

    // 更新队列中对应条目
    if (queueIdx !== undefined && queueIdx < importQueue.value.length) {
      const item = importQueue.value[queueIdx]
      item.step = stepText
      item.percent = percent
    }

    if (progress.status === 'completed') {
      importStep.value = '导入完成'
      importPercent.value = 100
      if (queueIdx === undefined) {
        importing.value = false
      } else if (queueIdx < importQueue.value.length) {
        importQueue.value[queueIdx].status = 'completed'
        importQueue.value[queueIdx].step = '已完成'
        importQueue.value[queueIdx].percent = 100
      }
      log.info('导入完成', { paperId: progress.paper_id })
      void loadPapers()
      return
    }

    if (progress.status === 'failed' || progress.status === 'error') {
      const errMsg = progress.error_msg || progress.step || '遇到了意外问题，请稍后重试'
      importStep.value = '导入失败'
      importError.value = errMsg
      importPercent.value = 100

      if (queueIdx === undefined) {
        importing.value = false
      } else if (queueIdx < importQueue.value.length) {
        importQueue.value[queueIdx].status = 'failed'
        importQueue.value[queueIdx].step = '导入失败'
        importQueue.value[queueIdx].percent = 100
        importQueue.value[queueIdx].error = errMsg
      }
      log.warn('导入失败', { paperId: progress.paper_id, step: progress.step, error: progress.error_msg })
    }
  }

  function applyImportStatus(status: ImportStatus, queueIdx?: number) {
    applyImportProgress({
      status: status.status,
      step: status.current_step,
      paper_id: status.paper_id,
      error_msg: status.error_msg,
      file_name: status.file_name,
      percent: status.percent,
    }, queueIdx)
  }

  async function monitorImportStatus(taskId: string, queueIdx?: number, maxConsecutiveFailures = 30) {
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
          importStep.value = '导入失败'
          importError.value = err.message || '导入失败'
          if (queueIdx === undefined) importing.value = false
          else if (queueIdx < importQueue.value.length) {
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
          importStep.value = '导入中断'
          if (!importError.value) importError.value = msg
          if (queueIdx === undefined) importing.value = false
          else if (queueIdx < importQueue.value.length) {
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

  async function importFile(file: File) {
    importing.value = true
    lastProgressSignature = ''
    importFileName.value = file.name
    importStep.value = '提交中...'
    importPercent.value = 2
    importError.value = null
    error.value = null
    log.info('开始导入论文', { name: file.name, size: file.size })

    try {
      const result = await startImport(file)
      importStep.value = '任务已创建，等待处理'
      importPercent.value = 8
      log.info('导入任务已创建', { taskId: result.task_id, fileName: file.name })
      await monitorImportStatus(result.task_id)
    } catch (err: unknown) {
      importing.value = false
      importError.value = err instanceof Error ? err.message : '导入失败'
      log.error('启动导入失败', err, { name: file.name })
      throw err
    }
  }

  async function importFiles(files: File[]) {
    if (files.length === 0) return
    if (files.length === 1) return importFile(files[0])

    importing.value = true
    importError.value = null
    error.value = null

    importQueue.value = files.map((f) => ({
      fileName: f.name,
      file: f,
      status: 'pending' as const,
      percent: 0,
      step: '等待中',
    }))

    let skippedCount = 0
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
        item.percent = 8
        item.step = '任务已创建，等待处理'
        log.info('导入任务已创建', { taskId: result.task_id, fileName: files[i].name })
        await monitorImportStatus(result.task_id, i)
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : '导入失败'
        // 重复导入：直接从队列移除，记入跳过
        if (msg.includes('已导入过')) {
          dupNames.push(item.fileName)
          importQueue.value.splice(i, 1)
          i-- // splice 后索引偏移
          skippedCount++
          continue
        }
        item.status = 'failed'
        item.error = msg
        item.step = '导入失败'
        log.error('批量导入中单文件失败', err, { name: files[i].name })
      }

      // 完成的条目短暂展示后立即移除
      if (importQueue.value[i]?.status === 'completed') {
        await wait(600)
        importQueue.value.splice(i, 1)
        i-- // splice 后索引偏移
      }
    }

    // 队列中剩余的都是真正失败的条目

    if (dupNames.length > 0) {
      importError.value = `${dupNames.length} 篇论文已导入过，已跳过：${dupNames.join('、')}`
    }

    importing.value = false
    void loadPapers()
  }

  function clearImportError() {
    importError.value = null
  }

  function clearImportQueue() {
    importQueue.value = []
  }

  function removeQueueItem(index: number) {
    importQueue.value.splice(index, 1)
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
    loading,
    error,
    selectedPaperIds,
    selectedPaperCount,
    paperCount,
    importing,
    importFileName,
    importStep,
    importPercent,
    importError,
    importQueue,
    loadPapers,
    removePaper,
    setSelectedPaperIds,
    togglePaperSelection,
    clearSelectedPapers,
    importFile,
    importFiles,
    monitorImportStatus,
    clearImportError,
    setImportError,
    clearImportQueue,
    removeQueueItem,
    retryQueueItem,
  }
})
