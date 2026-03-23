// 主题配置
export type ThemeId = 'deepseek' | 'academic' | 'notion' | 'dark'

export interface Theme {
  id: ThemeId
  name: string
  colors: {
    primary: string
    primaryHover: string
    primaryLight: string
    bgMain: string
    bgSidebar: string
    bgInput: string
    bgCard: string
    textPrimary: string
    textSecondary: string
    border: string
    borderFocus: string
  }
}

export const themes: Record<ThemeId, Theme> = {
  // DeepSeek 简约风 - 极简黑白灰
  deepseek: {
    id: 'deepseek',
    name: 'DeepSeek 简约',
    colors: {
      primary: '#5D5D5D',
      primaryHover: '#4A4A4A',
      primaryLight: '#7A7A7A',
      bgMain: '#FFFFFF',
      bgSidebar: '#FAFAFA',
      bgInput: '#F5F5F5',
      bgCard: '#FFFFFF',
      textPrimary: '#1A1A1A',
      textSecondary: '#8A8A8A',
      border: '#E8E8E8',
      borderFocus: '#5D5D5D'
    }
  },
  // 学术专业风 - Teal 青绿色
  academic: {
    id: 'academic',
    name: '学术专业',
    colors: {
      primary: '#0D9488',
      primaryHover: '#0F766E',
      primaryLight: '#14B8A6',
      bgMain: '#F0FDFA',
      bgSidebar: '#FFFFFF',
      bgInput: '#F8FAFC',
      bgCard: '#FFFFFF',
      textPrimary: '#134E4A',
      textSecondary: '#5EEAD4',
      border: '#CCFBF1',
      borderFocus: '#0D9488'
    }
  },
  // Notion 清新风 - 柔和白色
  notion: {
    id: 'notion',
    name: 'Notion 清新',
    colors: {
      primary: '#2EAADC',
      primaryHover: '#2386A8',
      primaryLight: '#5BC0DE',
      bgMain: '#FFFFFF',
      bgSidebar: '#FBFBFB',
      bgInput: '#F7F7F5',
      bgCard: '#FFFFFF',
      textPrimary: '#37352F',
      textSecondary: '#787774',
      border: '#E9E9E7',
      borderFocus: '#2EAADC'
    }
  },
  // 暗夜模式 - 深色主题
  dark: {
    id: 'dark',
    name: '暗夜模式',
    colors: {
      primary: '#10A37F',
      primaryHover: '#0D8A6A',
      primaryLight: '#1AB38D',
      bgMain: '#1C1C1E',
      bgSidebar: '#2C2C2E',
      bgInput: '#3A3A3C',
      bgCard: '#2C2C2E',
      textPrimary: '#E5E5E7',
      textSecondary: '#8E8E93',
      border: '#3A3A3C',
      borderFocus: '#10A37F'
    }
  }
}

import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  const currentThemeId = ref<ThemeId>('deepseek')

  // 应用主题到 CSS 变量
  function applyTheme(themeId: ThemeId) {
    const theme = themes[themeId]
    const root = document.documentElement

    Object.entries(theme.colors).forEach(([key, value]) => {
      // 转换 camelCase 到 kebab-case
      const cssKey = '--' + key.replace(/([A-Z])/g, '-$1').toLowerCase()
      root.style.setProperty(cssKey, value)
    })
  }

  // 初始化时应用主题
  watch(currentThemeId, (newId) => {
    applyTheme(newId)
  }, { immediate: true })

  function setTheme(themeId: ThemeId) {
    currentThemeId.value = themeId
  }

  function getCurrentTheme() {
    return themes[currentThemeId.value]
  }

  return {
    currentThemeId,
    themes,
    setTheme,
    getCurrentTheme
  }
})
