import { ref, type ComputedRef, type Ref } from 'vue'
import type { SourceCard } from '../types/source'

export interface CitationPreviewOptions {
  allSources: ComputedRef<SourceCard[]>
  isWPSAvailable: Ref<boolean> | ComputedRef<boolean>
  openReader: (paperId: string, page?: number) => void
  demoActive: { value: boolean }
}

/**
 * 引用悬浮预览 + 点击处理逻辑。
 * 管理预览浮窗的显示/隐藏定时器、位置、来源匹配。
 */
export function useCitationPreview(opts: CitationPreviewOptions) {
  const previewVisible = ref(false)
  const previewSource = ref<SourceCard | null>(null)
  const previewX = ref(0)
  const previewY = ref(0)

  let hoverTimer: ReturnType<typeof setTimeout> | null = null
  let hideTimer: ReturnType<typeof setTimeout> | null = null

  function cancelHoverTimer() {
    if (hoverTimer) {
      clearTimeout(hoverTimer)
      hoverTimer = null
    }
  }

  function cancelHideTimer() {
    if (hideTimer) {
      clearTimeout(hideTimer)
      hideTimer = null
    }
  }

  function startHideTimer() {
    cancelHideTimer()
    hideTimer = setTimeout(() => {
      previewVisible.value = false
    }, 300)
  }

  function showCitationPreview(source: SourceCard) {
    cancelHoverTimer()
    cancelHideTimer()
    previewSource.value = source
    previewX.value = Math.max(window.innerWidth / 2 - 200, 20)
    previewY.value = Math.max(window.innerHeight / 4, 20)
    previewVisible.value = true
  }

  function handleCitationHover(sourceId: string, event: MouseEvent) {
    cancelHoverTimer()
    cancelHideTimer()
    hoverTimer = setTimeout(() => {
      const src = opts.allSources.value.find((s) => s.id === sourceId)
      if (!src) return
      previewSource.value = src
      previewX.value = event.clientX
      previewY.value = event.clientY
      previewVisible.value = true
    }, 300)
  }

  function handleCitationLeave() {
    cancelHoverTimer()
    startHideTimer()
  }

  function handleCitationClick(sourceId: string) {
    const src = opts.allSources.value.find((s) => s.id === sourceId)
    if (!src) return

    if (!src.paper_id) {
      showCitationPreview(src)
      return
    }

    if (!opts.demoActive.value && opts.isWPSAvailable.value) {
      handleOpenSource(src)
      return
    }

    opts.openReader(src.paper_id, src.page)
  }

  function handleOpenSource(source: SourceCard) {
    const filePath = source.file_path || source.local_path
    if (!filePath) {
      showCitationPreview(source)
      return
    }

    if (opts.isWPSAvailable.value && window.wps?.OAAssist?.ShellExecute) {
      window.wps.OAAssist.ShellExecute(filePath)
    } else if (source.paper_id) {
      opts.openReader(source.paper_id, source.page)
    } else {
      showCitationPreview(source)
    }
  }

  function handlePreviewClick() {
    const src = previewSource.value
    if (!src) return
    previewVisible.value = false
    if (src.paper_id) {
      opts.openReader(src.paper_id, src.page)
    }
  }

  return {
    previewVisible,
    previewSource,
    previewX,
    previewY,
    handleCitationHover,
    handleCitationLeave,
    handleCitationClick,
    cancelHideTimer,
    startHideTimer,
    handlePreviewClick,
  }
}
