// frontend/src/composables/use-pdf-keyboard.ts
import { onMounted, onBeforeUnmount, type Ref } from 'vue'

interface KeyboardOptions {
  active: Ref<boolean>
  currentPage: Ref<number>
  totalPages: Ref<number>
  onClose: () => void
  onScrollToPage: (page: number) => void
  onZoomIn: () => void
  onZoomOut: () => void
  /** Open the Ctrl+F search bar */
  onOpenSearch?: () => void
  /** Whether search bar is currently open (for Escape handling) */
  isSearchOpen?: Ref<boolean>
}

export function usePdfKeyboard(options: KeyboardOptions) {
  function handleKeydown(e: KeyboardEvent) {
    if (!options.active.value) return

    const tag = (e.target as HTMLElement)?.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA') return

    switch (true) {
      case (e.key === 'f' || e.key === 'F') && (e.ctrlKey || e.metaKey):
        e.preventDefault()
        options.onOpenSearch?.()
        break

      case e.key === 'ArrowUp' || e.key === 'k':
        e.preventDefault()
        options.onScrollToPage(options.currentPage.value - 1)
        break

      case e.key === 'ArrowDown' || e.key === 'j':
        e.preventDefault()
        options.onScrollToPage(options.currentPage.value + 1)
        break

      case e.key === '+' || e.key === '=':
        e.preventDefault()
        options.onZoomIn()
        break

      case e.key === '-':
        e.preventDefault()
        options.onZoomOut()
        break

      case e.key === 'Home' && e.ctrlKey:
        e.preventDefault()
        options.onScrollToPage(1)
        break

      case e.key === 'End' && e.ctrlKey:
        e.preventDefault()
        options.onScrollToPage(options.totalPages.value)
        break

      case e.key === 'Escape':
        e.preventDefault()
        options.onClose()
        break

      default:
        break
    }
  }

  onMounted(() => {
    document.addEventListener('keydown', handleKeydown)
  })

  onBeforeUnmount(() => {
    document.removeEventListener('keydown', handleKeydown)
  })
}
