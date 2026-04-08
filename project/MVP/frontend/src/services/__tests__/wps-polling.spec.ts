import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import AppShell from '../../app/AppShell.vue'
import { useHostStore } from '../../stores/host'
import { WPS_POLLING_INTERVAL_MS, createWpsHostAdapter } from '../wps-host'

interface PollingSnapshotInput {
  available: boolean
  docTitle?: string
  text?: string
  throwsError?: boolean
}

function createPollingWpsApi(sequence: PollingSnapshotInput[]) {
  let callCount = 0

  return {
    WpsApplication() {
      const currentSnapshot = sequence[Math.min(callCount, sequence.length - 1)]
      callCount += 1

      if (currentSnapshot.throwsError) {
        throw new Error('宿主读取失败')
      }

      if (!currentSnapshot.available) {
        return {
          ActiveDocument: null,
        }
      }

      return {
        ActiveDocument: {
          Name: currentSnapshot.docTitle ?? '未命名论文.docx',
          Content: {
            Text: currentSnapshot.text ?? '',
          },
        },
      }
    },
  }
}

beforeEach(() => {
  // 每个测试都重新创建独立 Pinia，避免不同用例之间共享宿主状态。
  setActivePinia(createPinia())

  // Task 5 需要验证固定 5 秒轮询，所以这里统一切到假定时器。
  vi.useFakeTimers()
})

afterEach(() => {
  vi.clearAllTimers()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('WPS polling integration', () => {
  it('updates host store every 5 seconds with current document text snapshot', async () => {
    const hostStore = useHostStore()
    const host = createWpsHostAdapter(
      createPollingWpsApi([
        {
          available: true,
          docTitle: '论文草稿.docx',
          text: '第一版论文正文内容',
        },
        {
          available: true,
          docTitle: '论文草稿.docx',
          text: '第二版论文正文内容',
        },
      ]),
    )

    await host.startPolling(hostStore)

    expect(hostStore.available).toBe(true)
    expect(hostStore.docTitle).toBe('论文草稿.docx')
    expect(hostStore.text).toContain('第一版论文正文内容')
    expect(hostStore.updatedAt).toEqual(expect.any(String))

    await vi.advanceTimersByTimeAsync(WPS_POLLING_INTERVAL_MS - 1)
    expect(hostStore.text).toContain('第一版论文正文内容')

    await vi.advanceTimersByTimeAsync(1)
    expect(hostStore.text).toContain('第二版论文正文内容')

    host.stopPolling()
  })

  it('keeps the last successful snapshot when host read temporarily fails and recovers on the next poll', async () => {
    const hostStore = useHostStore()
    const host = createWpsHostAdapter(
      createPollingWpsApi([
        {
          available: true,
          docTitle: '论文草稿.docx',
          text: '第一次成功读取到的正文',
        },
        {
          available: true,
          throwsError: true,
        },
        {
          available: true,
          docTitle: '论文草稿（恢复）.docx',
          text: '第三次恢复后的正文',
        },
      ]),
    )

    await host.startPolling(hostStore)

    expect(hostStore.status).toBe('ready')
    expect(hostStore.available).toBe(true)
    expect(hostStore.docTitle).toBe('论文草稿.docx')
    expect(hostStore.text).toContain('第一次成功读取到的正文')
    const firstUpdatedAt = hostStore.updatedAt

    await vi.advanceTimersByTimeAsync(WPS_POLLING_INTERVAL_MS)

    // 这里必须锁死真实语义：宿主短暂读取异常只进入 stale，不能退化成 error。
    expect(hostStore.status).toBe('stale')
    expect(hostStore.available).toBe(true)
    expect(hostStore.docTitle).toBe('论文草稿.docx')
    expect(hostStore.text).toContain('第一次成功读取到的正文')
    expect(hostStore.updatedAt).toBe(firstUpdatedAt)

    await vi.advanceTimersByTimeAsync(WPS_POLLING_INTERVAL_MS)

    expect(hostStore.status).toBe('ready')
    expect(hostStore.available).toBe(true)
    expect(hostStore.docTitle).toBe('论文草稿（恢复）.docx')
    expect(hostStore.text).toContain('第三次恢复后的正文')
    expect(hostStore.updatedAt).toEqual(expect.any(String))
    expect(hostStore.updatedAt).not.toBe(firstUpdatedAt)

    host.stopPolling()
  })

  it('shows a neutral stale hint instead of no-document guidance when host read is temporarily stale', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const hostStore = useHostStore()
    hostStore.available = true
    hostStore.docTitle = '论文草稿.docx'
    hostStore.text = '已有正文'
    hostStore.updatedAt = '2026-03-25T10:00:00.000Z'
    hostStore.markStale()

    vi.stubGlobal(
      'wps',
      createPollingWpsApi([
        {
          available: true,
          throwsError: true,
        },
      ]),
    )

    const wrapper = mount(AppShell, {
      global: {
        plugins: [pinia],
      },
    })

    await nextTick()

    expect(hostStore.status).toBe('stale')
    expect(wrapper.text()).toContain('今天有什么可以帮到你？')
    expect(wrapper.text()).not.toContain('先在 WPS 文字中打开论文草稿')

    wrapper.unmount()
  })

  it('keeps the empty-state hero copy minimal even when hostStore.available changes', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)

    vi.stubGlobal(
      'wps',
      createPollingWpsApi([
        {
          available: false,
        },
        {
          available: true,
          docTitle: '毕业论文初稿.docx',
          text: '第二次轮询后读取到的论文正文',
        },
      ]),
    )

    const wrapper = mount(AppShell, {
      global: {
        plugins: [pinia],
      },
    })

    await nextTick()
    expect(wrapper.text()).toContain('今天有什么可以帮到你？')

    await vi.advanceTimersByTimeAsync(WPS_POLLING_INTERVAL_MS)
    await nextTick()

    // 新版首页空状态必须极简：不显示文档提示，不暴露标题。
    expect(wrapper.text()).toContain('今天有什么可以帮到你？')
    expect(wrapper.text()).not.toContain('已读取当前论文草稿')
    expect(wrapper.text()).not.toContain('毕业论文初稿.docx')

    wrapper.unmount()
  })
})
