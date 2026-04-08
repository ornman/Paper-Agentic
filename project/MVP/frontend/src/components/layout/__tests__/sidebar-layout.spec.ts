import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { setActivePinia } from 'pinia'
import AppShell from '../../../app/AppShell.vue'
import SidebarContainer from '../SidebarContainer.vue'
import TopNavBar from '../TopNavBar.vue'
import BottomActionBar from '../BottomActionBar.vue'
import EmptyState from '../../conversation/EmptyState.vue'
import HistoryDrawer from '../../overlays/HistoryDrawer.vue'

describe('SidebarContainer', () => {
  it('renders a unified shell chrome with product nav, proof-oriented knowledge bar, empty state, and action bar', () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({ data: [] }),
    }))
    vi.stubGlobal('fetch', fetchMock)

    const pinia = createPinia()
    setActivePinia(pinia)

    const wrapper = mount(SidebarContainer, {
      global: {
        plugins: [pinia],
      },
    })

    expect(wrapper.attributes('data-testid')).toBe('sidebar-container')
    expect(wrapper.attributes('data-sidebar-width')).toBe('380')
    expect(wrapper.attributes('aria-label')).toContain('WPS 论文创作辅助侧边栏')

    // Task 2 的关键不是新增功能，而是把壳层顶部整理成统一的产品 chrome。
    expect(wrapper.find('[data-testid="sidebar-chrome"]').exists()).toBe(true)

    expect(wrapper.findComponent(TopNavBar).exists()).toBe(true)
    expect(wrapper.findComponent(EmptyState).exists()).toBe(true)
    expect(wrapper.findComponent(BottomActionBar).exists()).toBe(true)

    expect(wrapper.find('[data-testid="top-nav"]').text()).toContain('新对话')

    wrapper.unmount()
    vi.unstubAllGlobals()
  })

  it('keeps the history drawer out of the DOM and shares the same shell rhythm contract with AppShell', () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({ data: [] }),
    }))
    vi.stubGlobal('fetch', fetchMock)

    const pinia = createPinia()
    setActivePinia(pinia)

    const wrapper = mount(SidebarContainer, {
      global: {
        plugins: [pinia],
      },
    })
    const appShellWrapper = mount(AppShell, {
      global: {
        plugins: [pinia],
      },
    })

    expect(wrapper.find('[data-testid="sidebar-main"]').exists()).toBe(true)
    expect(wrapper.findComponent(HistoryDrawer).exists()).toBe(true)
    expect(wrapper.find('[data-testid="history-drawer-shell"]').exists()).toBe(false)
    expect(wrapper.find('button[aria-label="关闭历史记录抽屉"]').exists()).toBe(false)

    expect(wrapper.find('[data-testid="bottom-action-bar"] button[aria-label="发送消息"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('新对话')

    expect(appShellWrapper.find('[data-testid="sidebar-chrome"]').exists()).toBe(true)
    expect(appShellWrapper.find('[data-testid="top-nav"]').text()).toContain('对话')

    wrapper.unmount()
    appShellWrapper.unmount()
    vi.unstubAllGlobals()
  })
})
