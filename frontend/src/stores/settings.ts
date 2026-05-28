import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useSettingsStore = defineStore('settings', () => {
  // ── API config ──
  const apiUrl = ref(localStorage.getItem('apiUrl') || '')
  const apiKey = ref(localStorage.getItem('apiKey') || '')
  const models = ref<string[]>(JSON.parse(localStorage.getItem('models') || '[]'))
  const selectedModel = ref(localStorage.getItem('selectedModel') || '')
  const thinkingEnabled = ref(localStorage.getItem('thinkingEnabled') !== 'false')

  // ── RAG params ──
  const chunkSize = ref(Number(localStorage.getItem('chunkSize')) || 500)
  const retrievalCount = ref(Number(localStorage.getItem('retrievalCount')) || 5)
  const temperature = ref(Number(localStorage.getItem('temperature')) || 0.7)
  const contextLength = ref(Number(localStorage.getItem('contextLength')) || 4096)

  // ── Font size ──
  const fontSize = ref(Number(localStorage.getItem('fontSize')) || 14)

  // ── Persistence ──
  function persist(key: string, value: string | number | boolean) {
    localStorage.setItem(key, String(value))
  }

  watch(apiUrl, (v) => persist('apiUrl', v))
  watch(apiKey, (v) => persist('apiKey', v))
  watch(selectedModel, (v) => {
    if (v) persist('selectedModel', v)
  })
  watch(thinkingEnabled, (v) => persist('thinkingEnabled', v))
  watch(chunkSize, (v) => persist('chunkSize', v))
  watch(retrievalCount, (v) => persist('retrievalCount', v))
  watch(temperature, (v) => persist('temperature', v))
  watch(contextLength, (v) => persist('contextLength', v))
  watch(fontSize, (v) => {
    persist('fontSize', v)
    document.documentElement.style.setProperty('--font-size-base', `${v}px`)
  })

  // ── Fetch models from API ──
  async function fetchModels() {
    if (!apiUrl.value || !apiKey.value) return
    try {
      let baseUrl = apiUrl.value.trim()
      if (baseUrl.endsWith('/')) baseUrl = baseUrl.slice(0, -1)

      const response = await fetch(`${baseUrl}/v1/models`, {
        headers: {
          Authorization: `Bearer ${apiKey.value}`,
          'User-Agent': 'AIForScience/1.0',
        },
      })

      if (response.ok) {
        const data = await response.json()
        if (data.data && Array.isArray(data.data)) {
          models.value = data.data.map((m: { id: string }) => m.id)
          localStorage.setItem('models', JSON.stringify(models.value))
          if (!models.value.includes(selectedModel.value)) {
            selectedModel.value = models.value[0] || ''
          }
        }
      }
    } catch {
      /* silently fail */
    }
  }

  // ── Clear cache (keep settings keys) ──
  function clearCache() {
    const keysToKeep = [
      'apiUrl', 'apiKey', 'selectedModel', 'models',
      'thinkingEnabled', 'fontSize', 'chunkSize',
      'retrievalCount', 'temperature', 'contextLength', 'theme-mode',
    ]
    const saved: Record<string, string> = {}
    keysToKeep.forEach((k) => {
      const v = localStorage.getItem(k)
      if (v) saved[k] = v
    })
    localStorage.clear()
    Object.entries(saved).forEach(([k, v]) => localStorage.setItem(k, v))
  }

  // ── Export data as JSON (excludes secrets) ──
  function exportData(): string {
    const data: Record<string, string> = {}
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key && !['apiKey'].includes(key)) {
        data[key] = localStorage.getItem(key) || ''
      }
    }
    return JSON.stringify(data, null, 2)
  }

  // ── Estimate localStorage usage ──
  function estimateStorageUsage(): string {
    let totalBytes = 0
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key) {
        const value = localStorage.getItem(key) || ''
        totalBytes += key.length + value.length
      }
    }
    // 2 bytes per char (UTF-16)
    const bytes = totalBytes * 2
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
  }

  // ── Apply font size on init ──
  if (fontSize.value !== 14) {
    document.documentElement.style.setProperty('--font-size-base', `${fontSize.value}px`)
  }

  return {
    apiUrl,
    apiKey,
    models,
    selectedModel,
    thinkingEnabled,
    chunkSize,
    retrievalCount,
    temperature,
    contextLength,
    fontSize,
    fetchModels,
    clearCache,
    exportData,
    estimateStorageUsage,
    toggleThinking() { thinkingEnabled.value = !thinkingEnabled.value },
  }
})
