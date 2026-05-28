import { ref, watch, onMounted, onUnmounted } from 'vue'

export type ThemeMode = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'theme-mode'

const mode = ref<ThemeMode>(loadSavedMode())
const resolvedTheme = ref<'light' | 'dark'>('light')

// Apply theme synchronously at module level to prevent FOUC
const initialMode = mode.value
const initialResolved = initialMode === 'system' ? resolveSystemPreference() : initialMode
if (typeof document !== 'undefined') {
  document.documentElement.setAttribute('data-theme', initialResolved)
}
resolvedTheme.value = initialResolved

function loadSavedMode(): ThemeMode {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved === 'light' || saved === 'dark' || saved === 'system') return saved
  return 'system'
}

function resolveSystemPreference(): 'light' | 'dark' {
  if (typeof window === 'undefined') return 'light'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(theme: 'light' | 'dark') {
  if (typeof document === 'undefined') return
  document.documentElement.setAttribute('data-theme', theme)
  resolvedTheme.value = theme
}

function resolveAndApply() {
  const resolved = mode.value === 'system' ? resolveSystemPreference() : mode.value
  applyTheme(resolved)
}

let mediaQuery: MediaQueryList | null = null

function handleMediaChange() {
  if (mode.value === 'system') {
    resolveAndApply()
  }
}

export function useTheme() {
  let cleanupFn: (() => void) | null = null

  onMounted(() => {
    if (typeof window === 'undefined') return

    mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    mediaQuery.addEventListener('change', handleMediaChange)
    cleanupFn = () => {
      mediaQuery?.removeEventListener('change', handleMediaChange)
    }
    resolveAndApply()
  })

  onUnmounted(() => {
    cleanupFn?.()
  })

  watch(mode, (next) => {
    localStorage.setItem(STORAGE_KEY, next)
    resolveAndApply()
  })

  function setMode(next: ThemeMode) {
    mode.value = next
  }

  function toggle() {
    const current = resolvedTheme.value
    mode.value = current === 'dark' ? 'light' : 'dark'
  }

  return {
    mode,
    resolvedTheme,
    setMode,
    toggle,
  }
}
