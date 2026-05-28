/**
 * WPS API 集成层
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
    SelectionChange: ((selection: any) => void) | null
  }
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

  function getSelectedText(): string {
    if (!isWPSAvailable.value || !wpsAPI.value) {
      return ''
    }

    try {
      const activeWindow = wpsAPI.value.ActiveWindow
      const selection = activeWindow?.Selection
      if (!selection) {
        return ''
      }

      const range = selection.Range
      if (range && range.Text) {
        const text = range.Text.trim()
        selectedText.value = text
        return text
      }

      const text = (selection.Text || '').trim()
      selectedText.value = text
      return text
    } catch (error) {
      logSelectionAccessFailure(error)
      return ''
    }
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
    getSelectedText,
    getDocumentContent,
    isWPSAvailable,
  }
}

const POLLING_INTERVAL = 5000

export function useWPSPolling(autoFill = true, sessionIdGetter?: () => string) {
  const { getSelectedText, getDocumentContent, isWPSAvailable } = useWPSSelection()
  const pollingTimer = ref<number | null>(null)
  const isPolling = ref(false)
  const lastSelection = ref('')
  const lastDocContent = ref('')

  function doPoll() {
    // ── 选区同步 ──
    const text = getSelectedText()
    if (text && text !== lastSelection.value) {
      if (autoFill && text.trim().length > 0) {
        const inputElement = document.querySelector('textarea.composer-input') as HTMLTextAreaElement | null
        if (inputElement && !inputElement.disabled) {
          inputElement.value = text
          inputElement.dispatchEvent(new Event('input', { bubbles: true }))
        }
      }
      lastSelection.value = text

      if (sessionIdGetter) {
        const sid = sessionIdGetter()
        if (sid && text.trim()) {
          updateSelection(sid, text).catch(() => {})
        }
      }
    }

    // ── 文档全文同步 ──
    if (sessionIdGetter) {
      const content = getDocumentContent()
      if (content && content !== lastDocContent.value) {
        lastDocContent.value = content
        const sid = sessionIdGetter()
        if (sid) {
          updateWrittenContext(sid, content).catch(() => {})
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
    getSelectedText,
    isWPSAvailable,
  }
}
