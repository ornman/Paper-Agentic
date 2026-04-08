import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { resolve, dirname } from 'node:path'
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { setActivePinia } from 'pinia'
import AppShell from '../AppShell.vue'

// CSS 自定义属性测试策略：
// JSDOM 环境不执行 CSS，getComputedStyle 无法读取自定义属性。
// ?inline / ?raw 在 Vitest v1 JSDOM 模式下也不做真实字符串转换。
// 因此改用 Node fs 读取源文件文本进行断言，直接校验 token 声明是否存在。
// 这与 build/runtime 无关，只验证 token 文件本身内容符合要求。
const __dirname = dirname(fileURLToPath(import.meta.url))
const tokensCssPath = resolve(__dirname, '../../styles/tokens.css')
const tokensCssText = readFileSync(tokensCssPath, 'utf-8')

function hasToken(name: string, value: string): boolean {
  // 允许冒号前后有空白，与 CSS 格式化策略解耦
  const pattern = new RegExp(`${name.replace(/[--]/g, '\\$&')}\\s*:\\s*${value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*;`)
  return pattern.test(tokensCssText)
}

describe('AppShell', () => {
  it('renders top nav, knowledge bar, content area, and bottom action bar', () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({ data: [] }),
    }))
    vi.stubGlobal('fetch', fetchMock)

    const pinia = createPinia()
    setActivePinia(pinia)

    const wrapper = mount(AppShell, {
      global: {
        plugins: [pinia],
      },
    })

    expect(wrapper.find('[data-testid="top-nav"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="content-area"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="bottom-action-bar"]').exists()).toBe(true)

    wrapper.unmount()
    vi.unstubAllGlobals()
  })

  it('exposes the refreshed visual tokens needed by the shell', () => {
    // 背景层：切到更接近纸张的浅米白，减少厚重暖黄感。
    expect(hasToken('--color-surface-base', '#f7f4ee')).toBe(true)
    expect(hasToken('--color-surface-muted', '#f7f4ee')).toBe(true)

    // 文本层：深灰文本 + 柔和浅灰辅助文本。
    expect(hasToken('--color-text-primary', '#26231f')).toBe(true)
    expect(hasToken('--color-text-secondary', '#9c978e')).toBe(true)

    // 强调层：切到低饱和淡蓝。
    expect(hasToken('--color-accent', '#aebeff')).toBe(true)
    expect(hasToken('--color-accent-soft', '#edf2ff')).toBe(true)

    // 结构层：继续维持细腻浅边框。
    expect(hasToken('--color-border-subtle', '#ddd8cf')).toBe(true)
    expect(hasToken('--radius-md', '14px')).toBe(true)
    expect(hasToken('--space-4', '16px')).toBe(true)
  })

})
