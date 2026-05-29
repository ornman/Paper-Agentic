import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { requestJsonData } from '../services/api-client'

export interface BackendConfig {
  data: Record<string, string>
  configured: {
    llm: boolean
    embedding: boolean
    mineru: boolean
  }
}

export const useSettingsStore = defineStore('settings', () => {
  // ── API config ──
  const apiUrl = ref(localStorage.getItem('apiUrl') || '')
  const apiKey = ref(localStorage.getItem('apiKey') || '')
  const models = ref<string[]>(JSON.parse(localStorage.getItem('models') || '[]'))
  const selectedModel = ref(localStorage.getItem('selectedModel') || '')
  const thinkingEnabled = ref(localStorage.getItem('thinkingEnabled') !== 'false')

  // ── Backend config status ──
  const backendConfigured = ref(localStorage.getItem('backendConfigured') === 'true')
  const configLoading = ref(false)

  // ── Conversation behavior ──
  const reflectionEnabled = ref(localStorage.getItem('reflectionEnabled') === 'true')
  const ragEnabled = ref(localStorage.getItem('ragEnabled') !== 'false')

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
  watch(reflectionEnabled, (v) => persist('reflectionEnabled', v))
  watch(ragEnabled, (v) => persist('ragEnabled', v))
  watch(backendConfigured, (v) => persist('backendConfigured', v))
  watch(fontSize, (v) => {
    persist('fontSize', v)
    document.documentElement.style.fontSize = `${v}px`
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
      'thinkingEnabled', 'reflectionEnabled', 'ragEnabled',
      'fontSize', 'theme-mode',
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
  document.documentElement.style.fontSize = `${fontSize.value}px`

  // ── Check backend config status ──
  async function fetchBackendConfig(): Promise<BackendConfig> {
    configLoading.value = true
    try {
      const config = await requestJsonData<BackendConfig>('/api/v1/config/env')
      backendConfigured.value = config.configured.llm && config.configured.embedding
      return config
    } catch {
      return { data: {}, configured: { llm: false, embedding: false, mineru: false } }
    } finally {
      configLoading.value = false
    }
  }

  return {
    apiUrl,
    apiKey,
    models,
    selectedModel,
    thinkingEnabled,
    reflectionEnabled,
    ragEnabled,
    fontSize,
    backendConfigured,
    configLoading,
    fetchModels,
    fetchBackendConfig,
    clearCache,
    exportData,
    estimateStorageUsage,
    toggleThinking() { thinkingEnabled.value = !thinkingEnabled.value },
  }
})
