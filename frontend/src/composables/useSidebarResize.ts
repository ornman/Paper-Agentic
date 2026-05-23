import { ref, onMounted, onUnmounted } from 'vue'

const MIN_WIDTH = 240
const MAX_WIDTH = 480
const DEFAULT_WIDTH = 320
const STORAGE_KEY = 'sidebarWidth'

export function useSidebarResize() {
  const sidebarWidth = ref(DEFAULT_WIDTH)
  const isResizing = ref(false)

  function handleResize(event: MouseEvent) {
    if (!isResizing.value) return
    const newWidth = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, event.clientX))
    sidebarWidth.value = newWidth
  }

  function stopResize() {
    if (!isResizing.value) return
    isResizing.value = false
    document.removeEventListener('mousemove', handleResize)
    document.removeEventListener('mouseup', stopResize)
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    localStorage.setItem(STORAGE_KEY, String(sidebarWidth.value))
  }

  function startResize(event: MouseEvent) {
    event.preventDefault()
    isResizing.value = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    document.addEventListener('mousemove', handleResize)
    document.addEventListener('mouseup', stopResize)
  }

  onMounted(() => {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      const parsed = parseInt(saved, 10)
      if (parsed >= MIN_WIDTH && parsed <= MAX_WIDTH) {
        sidebarWidth.value = parsed
      }
    }
  })

  onUnmounted(() => {
    document.removeEventListener('mousemove', handleResize)
    document.removeEventListener('mouseup', stopResize)
  })

  return { sidebarWidth, isResizing, startResize }
}
