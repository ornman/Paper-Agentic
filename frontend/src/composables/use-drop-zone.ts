import { ref } from 'vue'

/**
 * 拖拽上传区域逻辑。
 * 处理嵌套元素的 dragenter/dragleave 计数，避免闪烁。
 */
export function useDropZone(onDrop: (files: File[]) => void) {
  const dragActive = ref(false)
  let dragCounter = 0

  function onDragEnter() {
    dragCounter++
    dragActive.value = true
  }

  function onDragLeave() {
    dragCounter--
    if (dragCounter <= 0) {
      dragCounter = 0
      dragActive.value = false
    }
  }

  function handleDrop(e: DragEvent) {
    dragCounter = 0
    dragActive.value = false
    const files = e.dataTransfer?.files
    if (!files || files.length === 0) return
    const pdfFiles = Array.from(files).filter((f) => f.name.toLowerCase().endsWith('.pdf'))
    if (pdfFiles.length > 0) {
      onDrop(pdfFiles)
    }
  }

  return { dragActive, onDragEnter, onDragLeave, onDrop: handleDrop }
}
