import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useSettingsStore = defineStore('settings', () => {
  const selectedModel = ref(localStorage.getItem('selectedModel') || '')
  const thinkingEnabled = ref(localStorage.getItem('thinkingEnabled') !== 'false')

  return { selectedModel, thinkingEnabled }
})
