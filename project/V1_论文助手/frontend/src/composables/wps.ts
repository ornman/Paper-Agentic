/**
 * WPS API 集成层
 */

import { ref, onMounted, onUnmounted } from 'vue'
import { useLogger } from './logger'

const log = useLogger('wps')
const ERROR_LOG_INTERVAL = 30000
let lastSelectionErrorLogAt = 0

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

interface SelectionInfo {
  text: string
  start: number
  end: number
}

function logSelectionAccessFailure(error: unknown) {
  const now = Date.now()
  if (now - lastSelectionErrorLogAt < ERROR_LOG_INTERVAL) {
    return
  }
  lastSelectionErrorLogAt = now
  log.warn('获取选中文字失败', error instanceof Error ? error.message : String(error))
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
  const selectionInfo = ref<SelectionInfo | null>(null)

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
        selectionInfo.value = {
          text,
          start: 0,
          end: text.length,
        }
        return text
      }

      const text = (selection.Text || '').trim()
      selectedText.value = text
      selectionInfo.value = {
        text,
        start: 0,
        end: text.length,
      }
      return text
    } catch (error) {
      logSelectionAccessFailure(error)
      return ''
    }
  }

  return {
    selectedText,
    selectionInfo,
    getSelectedText,
    isWPSAvailable,
  }
}

const POLLING_INTERVAL = 5000

export function useWPSPolling(autoFill = true) {
  const { getSelectedText, isWPSAvailable } = useWPSSelection()
  const pollingTimer = ref<number | null>(null)
  const isPolling = ref(false)
  const lastSelection = ref('')

  function doPoll() {
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

export async function openExternalUrl(url: string): Promise<void> {
  if (typeof window !== 'undefined') {
    const shellExecute = window.wps?.OAAssist?.ShellExecute
      ?? (globalThis as { wps?: { OAAssist?: { ShellExecute?: (url: string, params?: string) => void } } }).wps?.OAAssist?.ShellExecute

    if (typeof shellExecute === 'function') {
      shellExecute(url, '')
      return
    }

    window.open(url, '_blank', 'noopener,noreferrer')
    return
  }

  throw new Error('当前环境不支持打开外部链接')
}

export function useWPSSelectionChange() {
  const { wpsAPI, isWPSAvailable } = useWPSDetection()
  const currentSelection = ref('')

  function handleSelectionChange(selection: any) {
    try {
      const text = selection.Text || ''
      if (text && text !== currentSelection.value) {
        currentSelection.value = text
        const inputElement = document.querySelector('textarea.composer-input') as HTMLTextAreaElement | null
        if (inputElement && !inputElement.disabled && text.trim().length > 0) {
          inputElement.value = text
          inputElement.dispatchEvent(new Event('input', { bubbles: true }))
        }
      }
    } catch (error) {
      logSelectionAccessFailure(error)
    }
  }

  function bindSelectionChange() {
    if (!isWPSAvailable.value || !wpsAPI.value) {
      return false
    }

    try {
      const app = wpsAPI.value
      if (!app.ActiveWindow) {
        return false
      }

      app.ActiveWindow.SelectionChange = handleSelectionChange
      return true
    } catch (error) {
      logSelectionAccessFailure(error)
      return false
    }
  }

  function unbindSelectionChange() {
    if (!isWPSAvailable.value || !wpsAPI.value) {
      return
    }

    try {
      const app = wpsAPI.value
      if (app && app.ActiveWindow) {
        app.ActiveWindow.SelectionChange = null
      }
    } catch (error) {
      logSelectionAccessFailure(error)
    }
  }

  onUnmounted(() => {
    unbindSelectionChange()
  })

  return {
    bindSelectionChange,
    unbindSelectionChange,
    currentSelection,
    isWPSAvailable,
  }
}
