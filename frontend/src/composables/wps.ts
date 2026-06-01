/**
 * WPS API 集成层
 *
 * 架构：事件驱动（加速路径）+ 轮询（兜底路径）双保险
 * - SelectionChange 事件 → 立即推送选区（300ms debounce）
 * - 轮询定时器（3s 间隔）→ 兜底检测选区 + 文档全文变化
 */

import { ref, onMounted, onUnmounted } from 'vue'
import { useLogger } from './logger'
import { updateSelection, updateWrittenContext } from '../services/assistant-api'

const log = useLogger('wps')
const ERROR_LOG_INTERVAL = 30000
let lastSelectionErrorLogAt = 0
let lastDocContentErrorLogAt = 0

declare global {
  interface Window {
    wps?: {
      WpsApplication(): WPSApplication
      OAAssist?: {
        ShellExecute?: (url: string, params?: string) => void
      }
    }
  }
}

interface WPSApplication {
  ActiveDocument: {
    Content: {
      Text: string
    }
  }
  ActiveWindow: {
    Selection: {
      Text: string
      Start: number
      End: number
      Range: {
        Text: string
      }
    }
    SelectionChange: ((selection: unknown) => void) | null
  }
}

/** 完整的选区信息，包含文档中的真实偏移量 */
export interface SelectionInfo {
  text: string
  start: number
  end: number
  source: 'selection' | 'range'
}

function logSelectionAccessFailure(error: unknown) {
  const now = Date.now()
  if (now - lastSelectionErrorLogAt < ERROR_LOG_INTERVAL) {
    return
  }
  lastSelectionErrorLogAt = now
  log.warn('获取选中文字失败', error instanceof Error ? error.message : String(error))
}

function logDocContentAccessFailure(error: unknown) {
  const now = Date.now()
  if (now - lastDocContentErrorLogAt < ERROR_LOG_INTERVAL) {
    return
  }
  lastDocContentErrorLogAt = now
  log.warn('获取文档全文失败', error instanceof Error ? error.message : String(error))
}

export function useWPSDetection() {
  const isWPSAvailable = ref(false)
  const wpsAPI = ref<WPSApplication | null>(null)

  function detectWPS() {
    if (typeof window !== 'undefined' && window.wps) {
      try {
        wpsAPI.value = window.wps.WpsApplication()
        isWPSAvailable.value = !!wpsAPI.value
        log.info('WPS API 检测成功')
      } catch (error) {
        log.error('WPS API 检测失败', error)
        isWPSAvailable.value = false
      }
    } else {
      isWPSAvailable.value = false
    }
  }

  onMounted(() => {
    detectWPS()
  })

  return {
    isWPSAvailable,
    wpsAPI,
  }
}

export function useWPSSelection() {
  const { wpsAPI, isWPSAvailable } = useWPSDetection()
  const selectedText = ref('')

  /** 获取完整选区信息（含真实文档偏移量） */
  function getSelectionInfo(): SelectionInfo | null {
    if (!isWPSAvailable.value || !wpsAPI.value) {
      return null
    }

    try {
      const activeWindow = wpsAPI.value.ActiveWindow
      const selection = activeWindow?.Selection
      if (!selection) {
        return null
      }

      // 优先用 Range（有真实偏移量）
      const range = selection.Range
      if (range?.Text) {
        const text = range.Text.trim()
        if (!text) return null
        selectedText.value = text
        return {
          text,
          start: selection.Start,
          end: selection.End,
          source: 'range',
        }
      }

      // fallback：用 Selection.Text
      const text = (selection.Text || '').trim()
      if (!text) return null
      selectedText.value = text
      return {
        text,
        start: selection.Start,
        end: selection.End,
        source: 'selection',
      }
    } catch (error) {
      logSelectionAccessFailure(error)
      return null
    }
  }

  /** @deprecated 使用 getSelectionInfo() 获取完整选区信息 */
  function getSelectedText(): string {
    const info = getSelectionInfo()
    return info?.text ?? ''
  }

  function getDocumentContent(): string {
    if (!isWPSAvailable.value || !wpsAPI.value) {
      return ''
    }

    try {
      const doc = wpsAPI.value.ActiveDocument
      if (!doc?.Content?.Text) {
        return ''
      }
      return doc.Content.Text.trim()
    } catch (error) {
      logDocContentAccessFailure(error)
      return ''
    }
  }

  return {
    selectedText,
    getSelectionInfo,
    getSelectedText,
    getDocumentContent,
    isWPSAvailable,
  }
}

// ── 事件驱动的选区监听（加速路径） ──

const SELECTION_DEBOUNCE_MS = 300
const REBIND_INTERVAL = 2000

export function useWPSSelectionChange(
  onChanged: (info: SelectionInfo) => void,
) {
  const { wpsAPI, isWPSAvailable } = useWPSDetection()
  let debounceTimer: ReturnType<typeof setTimeout> | null = null
  let rebindTimer: ReturnType<typeof setInterval> | null = null

  function bindHandler() {
    if (!isWPSAvailable.value || !wpsAPI.value) return
    const win = wpsAPI.value.ActiveWindow
    if (!win) return

    win.SelectionChange = () => {
      if (debounceTimer) clearTimeout(debounceTimer)
      debounceTimer = setTimeout(() => {
        const info = getSelectionInfoInternal()
        if (info) onChanged(info)
      }, SELECTION_DEBOUNCE_MS)
    }
  }

  function getSelectionInfoInternal(): SelectionInfo | null {
    if (!isWPSAvailable.value || !wpsAPI.value) return null
    try {
      const selection = wpsAPI.value.ActiveWindow?.Selection
      if (!selection) return null
      const range = selection.Range
      if (range?.Text) {
        const text = range.Text.trim()
        if (!text) return null
        return { text, start: selection.Start, end: selection.End, source: 'range' }
      }
      const text = (selection.Text || '').trim()
      if (!text) return null
      return { text, start: selection.Start, end: selection.End, source: 'selection' }
    } catch {
      return null
    }
  }

  function startRebindWatch() {
    rebindTimer = setInterval(() => {
      if (isWPSAvailable.value) {
        bindHandler()
      }
    }, REBIND_INTERVAL)
  }

  function stopRebindWatch() {
    if (rebindTimer) {
      clearInterval(rebindTimer)
      rebindTimer = null
    }
  }

  onUnmounted(() => {
    if (debounceTimer) clearTimeout(debounceTimer)
    stopRebindWatch()
  })

  return { bindHandler, startRebindWatch, stopRebindWatch }
}

// ── 轮询（兜底路径） ──

const POLLING_INTERVAL = 3000
const DOC_SYNC_THROTTLE_MS = 10000

export function useWPSPolling(autoFill = true, sessionIdGetter?: () => string) {
  const { getSelectionInfo, getDocumentContent, isWPSAvailable } = useWPSSelection()
  const pollingTimer = ref<number | null>(null)
  const isPolling = ref(false)
  const lastSelectionKey = ref('')
  const lastDocContent = ref('')
  const lastDocSyncAt = ref(0)

  function selectionKey(info: SelectionInfo): string {
    return `${info.text}|${info.start}|${info.end}`
  }

  function doPoll() {
    // ── 选区同步 ──
    const info = getSelectionInfo()
    if (info) {
      const key = selectionKey(info)
      if (key !== lastSelectionKey.value) {
        if (autoFill && info.text.trim().length > 0) {
          const inputElement = document.querySelector('textarea.composer-textarea') as HTMLTextAreaElement | null
          if (inputElement && !inputElement.disabled) {
            inputElement.value = info.text
            inputElement.dispatchEvent(new Event('input', { bubbles: true }))
          }
        }
        lastSelectionKey.value = key

        if (sessionIdGetter) {
          const sid = sessionIdGetter()
          if (sid && info.text.trim()) {
            updateSelection(sid, info.text, info.start, info.end).catch(() => {})
          }
        }
      }
    }

    // ── 文档全文同步（throttle 10s） ──
    if (sessionIdGetter) {
      const now = Date.now()
      if (now - lastDocSyncAt.value >= DOC_SYNC_THROTTLE_MS) {
        const content = getDocumentContent()
        if (content && content !== lastDocContent.value) {
          lastDocContent.value = content
          lastDocSyncAt.value = now
          const sid = sessionIdGetter()
          if (sid) {
            updateWrittenContext(sid, content).catch(() => {})
          }
        }
      }
    }
  }

  function startPolling() {
    if (!isWPSAvailable.value || pollingTimer.value) {
      return
    }

    isPolling.value = true
    doPoll()
    pollingTimer.value = window.setInterval(doPoll, POLLING_INTERVAL) as unknown as number
  }

  function stopPolling() {
    if (!pollingTimer.value) {
      return
    }

    clearInterval(pollingTimer.value)
    pollingTimer.value = null
    isPolling.value = false
  }

  onUnmounted(() => {
    stopPolling()
  })

  return {
    isPolling,
    startPolling,
    stopPolling,
    getSelectionInfo,
    isWPSAvailable,
  }
}
