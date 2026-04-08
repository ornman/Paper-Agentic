import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useHostStore } from '../host'
import { useLibraryStore } from '../library'
import { useConversationStore } from '../conversation'
import { useUiStore } from '../ui'

beforeEach(() => {
  // 每个用例都重新创建 Pinia，避免 store 状态在测试之间互相污染。
  setActivePinia(createPinia())
})

describe('host store state machine', () => {
  it('starts in booting and transitions through the minimal host lifecycle', () => {
    const store = useHostStore()

    expect(store.status).toBe('booting')
    expect(store.errorMessage).toBe(null)

    store.markReady()
    expect(store.status).toBe('ready')

    store.markPolling()
    expect(store.status).toBe('polling')

    store.markStale()
    expect(store.status).toBe('stale')

    store.markNoDocument()
    expect(store.status).toBe('no_document')
  })

  it('moves to error and keeps the latest error message', () => {
    const store = useHostStore()

    store.markError('宿主轮询失败')

    expect(store.status).toBe('error')
    expect(store.errorMessage).toBe('宿主轮询失败')
  })
})

describe('library store state machine', () => {
  it('starts unavailable and transitions to empty, importing, and ready', () => {
    const store = useLibraryStore()

    expect(store.status).toBe('unavailable')
    expect(store.errorMessage).toBe(null)

    store.markEmpty()
    expect(store.status).toBe('empty')

    store.startImporting()
    expect(store.status).toBe('importing')

    store.markReady()
    expect(store.status).toBe('ready')
  })

  it('moves to error and keeps the latest import error message', () => {
    const store = useLibraryStore()

    store.markError('导入失败')

    expect(store.status).toBe('error')
    expect(store.errorMessage).toBe('导入失败')
  })
})

describe('conversation store state machine', () => {
  it('transitions conversation state from idle to requesting to streaming to done', () => {
    const store = useConversationStore()

    expect(store.status).toBe('idle')
    expect(store.errorMessage).toBe(null)

    store.startRequest()
    expect(store.status).toBe('requesting')

    store.startStreaming()
    expect(store.status).toBe('streaming')

    store.finishResponse()
    expect(store.status).toBe('done')
  })

  it('moves to error and can be reset back to idle', () => {
    const store = useConversationStore()

    store.markError('请求失败')
    expect(store.status).toBe('error')
    expect(store.errorMessage).toBe('请求失败')

    store.reset()
    expect(store.status).toBe('idle')
    expect(store.errorMessage).toBe(null)
  })
})

describe('ui store', () => {
  it('controls history drawer and sidebar expansion state', () => {
    const store = useUiStore()

    expect(store.historyDrawerOpen).toBe(false)
    expect(store.sidebarExpanded).toBe(true)
    expect(store.toastMessage).toBe(null)

    store.openHistoryDrawer()
    expect(store.historyDrawerOpen).toBe(true)

    store.closeHistoryDrawer()
    expect(store.historyDrawerOpen).toBe(false)

    store.toggleSidebarExpanded()
    expect(store.sidebarExpanded).toBe(false)
  })

  it('shows and clears toast messages', () => {
    const store = useUiStore()

    store.showToast('文档已加入知识库')
    expect(store.toastMessage).toBe('文档已加入知识库')

    store.clearToast()
    expect(store.toastMessage).toBe(null)
  })
})
