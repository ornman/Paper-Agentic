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
  createImportStream,
} from '../services/library-api'
import type { PaperItem, ImportQueueItem, ImportProgressEvent } from '../types/paper'
import type { ImportSseStatus, ImportStep } from '../types/paper'
import { ApiClientError } from '../services/api-client'
import { useLogger } from '../composables/logger'

const log = useLogger('api')

// ─── 步骤中文标签 ────────────────────────────────────────

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

// ─── 队列持久化 ──────────────────────────────────────────

const STORAGE_KEY = 'paper-agentic-import-queue'

function persistQueue(items: ImportQueueItem[]): void {
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

// ─── SSE 进度事件解析 ────────────────────────────────────

interface RawSseProgress {
  status: ImportSseStatus
  step: ImportStep | null
  percent: number
  stage_name: string | null
  paper_id: string | null
  error_msg: string | null
}

function parseSseProgress(data: string): RawSseProgress {
  try {
    const parsed = JSON.parse(data)
    return {
      status: parsed.status ?? 'running',
      step: parsed.step ?? null,
      percent: typeof parsed.percent === 'number' ? parsed.percent : 0,
      stage_name: parsed.stage_name ?? null,
      paper_id: parsed.paper_id ?? null,
      error_msg: parsed.error_msg ?? null,
    }
  } catch {
    return { status: 'running', step: null, percent: 0, stage_name: null, paper_id: null, error_msg: null }
  }
}

// ─── Store ───────────────────────────────────────────────

export const useLibraryStore = defineStore('library', () => {
  const papers = ref<PaperItem[]>([])
  const trashedPapers = ref<PaperItem[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const selectedPaperIds = ref<string[]>([])

  const importQueue = ref<ImportQueueItem[]>(restoreQueue())
  const importError = ref<string | null>(null)

  // ─── Computed ──────────────────────────────────────────

  const selectedPaperCount = computed(() => selectedPaperIds.value.length)
  const paperCount = computed(() => papers.value.length)
  const isImporting = computed(() =>
    importQueue.value.some((item) => item.status === 'importing' || item.status === 'pending'),
  )

  // ─── 论文列表加载 ─────────────────────────────────────

  async function loadPapers(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const result = await fetchPapers()
      papers.value = result
      log.info('加载论文列表成功', { count: result.length })
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : '加载论文列表失败'
      log.error('加载论文列表失败', err)
    } finally {
      loading.value = false
    }
  }

  // ─── 导入进度应用 ─────────────────────────────────────

  function applyProgress(queueIdx: number, progress: ImportProgressEvent): void {
    if (queueIdx < 0 || queueIdx >= importQueue.value.length) return

    const item = importQueue.value[queueIdx]
    const stepText = progress.error_msg
      || STEP_LABELS[progress.step ?? '']
      || progress.step
      || '处理中...'

    if (typeof progress.percent === 'number' && progress.percent > 0) {
      item.percent = progress.percent
    }

    item.step = stepText

    if (progress.status === 'completed') {
      item.status = 'completed'
      item.step = '已完成'
      item.percent = 100
      log.info('导入完成', { paperId: progress.paper_id })
      // 延迟 2 秒自动移除已完成项
      const fileName = item.fileName
      window.setTimeout(() => {
        const idx = importQueue.value.findIndex((q) => q.fileName === fileName && q.status === 'completed')
        if (idx !== -1) {
          importQueue.value = importQueue.value.filter((_, i) => i !== idx)
          persistQueue(importQueue.value)
        }
      }, 2000)
      void loadPapers()
      return
    }

    if (progress.status === 'failed' || progress.status === 'stage_failed') {
      const errMsg = progress.error_msg || '遇到了意外问题，请稍后重试'
      item.status = 'failed'
      item.step = '导入失败'
      item.percent = 100
      item.error = errMsg
      log.warn('导入失败', { paperId: progress.paper_id, step: progress.step, error: progress.error_msg })
    }
  }

  // ─── SSE 实时监控 ─────────────────────────────────────

  function monitorViaSSE(taskId: string, queueIdx: number): Promise<void> {
    return new Promise((resolve) => {
      const es = createImportStream(taskId)

      es.addEventListener('progress', (event: MessageEvent) => {
        const raw = parseSseProgress(event.data)
        applyProgress(queueIdx, {
          status: raw.status,
          step: raw.step,
          percent: raw.percent,
          paper_id: raw.paper_id,
          error_msg: raw.error_msg,
        })

        if (raw.status === 'completed' || raw.status === 'failed' || raw.status === 'done') {
          es.close()
          resolve()
        }
      })

      es.onerror = () => {
        es.close()
        // SSE 失败，降级到轮询
        log.warn('SSE 连接失败，降级到轮询', { taskId })
        void monitorViaPolling(taskId, queueIdx).then(resolve)
      }

      // 安全超时：10 分钟无终态则关闭
      window.setTimeout(() => {
        if (es.readyState !== EventSource.CLOSED) {
          es.close()
          resolve()
        }
      }, 600_000)
    })
  }

  // ─── 轮询降级 ─────────────────────────────────────────

  function wait(ms: number): Promise<void> {
    return new Promise((r) => window.setTimeout(r, ms))
  }

  async function monitorViaPolling(taskId: string, queueIdx: number, maxFailures = 30): Promise<void> {
    let consecutiveFailures = 0

    while (true) {
      try {
        const status = await fetchImportStatus(taskId)
        consecutiveFailures = 0

        // 轮询没有 percent，基于 status 估算
        let estimatedPercent = 0
        if (queueIdx < importQueue.value.length) {
          estimatedPercent = Math.min(importQueue.value[queueIdx].percent + 8, 95)
        }

        applyProgress(queueIdx, {
          status: status.status,
          step: status.current_step,
          percent: estimatedPercent,
          paper_id: status.paper_id,
          error_msg: status.error_msg,
        })

        if (status.status === 'completed' || status.status === 'failed') return
      } catch (err: unknown) {
        if (err instanceof ApiClientError && err.statusCode === 400) {
          if (queueIdx < importQueue.value.length) {
            const item = importQueue.value[queueIdx]
            item.status = 'failed'
            item.step = '导入失败'
            item.error = err.message
          }
          log.warn('导入任务返回业务错误', { taskId, message: err.message })
          return
        }

        consecutiveFailures += 1
        log.warn('轮询导入状态失败', {
          taskId, consecutiveFailures,
          message: err instanceof Error ? err.message : String(err),
        })

        if (consecutiveFailures >= maxFailures) {
          if (queueIdx < importQueue.value.length) {
            const item = importQueue.value[queueIdx]
            item.status = 'failed'
            item.step = '导入中断'
            item.error = '导入似乎中断了，请尝试重新上传'
          }
          return
        }
      }

      await wait(2000)
    }
  }

  // ─── 断点续传 ─────────────────────────────────────────

  async function resumeImports(): Promise<void> {
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

    for (let i = 0; i < importQueue.value.length; i++) {
      const item = importQueue.value[i]
      if (item.status !== 'importing' && item.status !== 'pending') continue

      if (item.taskId) {
        // 有 taskId，直接监控（优先 SSE）
        try {
          await monitorViaSSE(item.taskId, i)
        } catch {
          item.status = 'failed'
          item.step = '导入失败（刷新后恢复）'
        }
      } else if (item.file) {
        // 无 taskId 但有 file，重新提交
        try {
          const result = await startImport(item.file)
          item.taskId = result.task_id
          item.status = 'importing'
          item.percent = 8
          item.step = '任务已创建，等待处理'
          await monitorViaSSE(result.task_id, i)
        } catch {
          item.status = 'failed'
          item.step = '导入失败'
        }
      }
    }

    persistQueue(importQueue.value)
    void loadPapers()
  }

  // ─── 删除 / 回收站 ────────────────────────────────────

  async function removePaper(paperId: string): Promise<void> {
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

  async function loadTrashedPapers(): Promise<void> {
    try {
      trashedPapers.value = await fetchTrashedPapers()
      log.info('加载回收站列表成功', { count: trashedPapers.value.length })
    } catch (err: unknown) {
      log.error('加载回收站列表失败', err)
    }
  }

  async function restorePaperFromTrash(paperId: string): Promise<void> {
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

  async function permanentDeleteFromTrash(paperId: string): Promise<void> {
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

  // ─── 选择管理 ──────────────────────────────────────────

  function setSelectedPaperIds(ids: string[]): void {
    selectedPaperIds.value = [...new Set(ids)]
  }

  function togglePaperSelection(paperId: string): void {
    if (selectedPaperIds.value.includes(paperId)) {
      selectedPaperIds.value = selectedPaperIds.value.filter((id) => id !== paperId)
    } else {
      selectedPaperIds.value = [...selectedPaperIds.value, paperId]
    }
  }

  function clearSelectedPapers(): void {
    selectedPaperIds.value = []
  }

  // ─── 导入流程 ──────────────────────────────────────────

  async function importFiles(files: File[]): Promise<void> {
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

      try {
        const result = await startImport(files[i])
        item.taskId = result.task_id
        item.percent = 8
        item.step = '任务已创建，等待处理'
        persistQueue(importQueue.value)
        log.info('导入任务已创建', { taskId: result.task_id, fileName: files[i].name })
        await monitorViaSSE(result.task_id, i)
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : '导入失败'
        if (msg.includes('已导入过')) {
          dupNames.push(item.fileName)
          importQueue.value = importQueue.value.filter((_, idx) => idx !== i)
          i--
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

    // 清理已完成的队列项，只保留失败的
    importQueue.value = importQueue.value.filter((item) => item.status === 'failed')

    if (dupNames.length > 0) {
      importError.value = `${dupNames.length} 篇论文已导入过，已跳过：${dupNames.join('、')}`
    }

    persistQueue(importQueue.value)
  }

  // ─── 队列操作 ──────────────────────────────────────────

  function clearImportError(): void {
    importError.value = null
  }

  function setImportError(message: string | null): void {
    importError.value = message
  }

  function clearImportQueue(): void {
    importQueue.value = []
    persistQueue(importQueue.value)
  }

  function removeQueueItem(index: number): void {
    importQueue.value = importQueue.value.filter((_, i) => i !== index)
    persistQueue(importQueue.value)
  }

  /** 重试失败的导入项（重新上传文件） */
  async function retryQueueItem(index: number): Promise<void> {
    const item = importQueue.value[index]
    if (!item?.file) return

    item.status = 'importing'
    item.percent = 2
    item.step = '提交中...'
    item.error = undefined

    try {
      const result = await startImport(item.file)
      item.percent = 8
      item.step = '任务已创建，等待处理'
      log.info('重试导入', { taskId: result.task_id, fileName: item.fileName })
      await monitorViaSSE(result.task_id, index)
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
    clearImportError,
    setImportError,
    clearImportQueue,
    removeQueueItem,
    retryQueueItem,
  }
})
