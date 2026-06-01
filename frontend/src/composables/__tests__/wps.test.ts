/**
 * WPS 集成层单元测试
 *
 * 覆盖：useWPSDetection, useWPSSelection (getSelectionInfo/getDocumentContent),
 *       useWPSSelectionChange (debounce/rebind)
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'

import { useWPSDetection, useWPSSelection, useWPSSelectionChange } from '../wps'
import type { SelectionInfo } from '../wps'
import { createMockWPSEnvironment, removeMockWPS } from './wps.mock'
import type { MockWPSEnvironment } from './wps.mock'

// ── Helpers ──────────────────────────────────────────────

/** 在 Vue 组件上下文中运行 composable */
function withSetup<T>(composable: () => T): T {
  let result!: T
  const Comp = defineComponent({
    setup() {
      result = composable()
      return () => null
    },
  })
  mount(Comp)
  return result
}

// ── useWPSDetection ──────────────────────────────────────

describe('useWPSDetection', () => {
  describe('WPS API 可用时', () => {
    beforeEach(() => {
      createMockWPSEnvironment()
    })

    afterEach(() => {
      removeMockWPS()
    })

    it('应该检测到 WPS API 并设置 isWPSAvailable = true', () => {
      const { isWPSAvailable, wpsAPI } = withSetup(useWPSDetection)

      expect(isWPSAvailable.value).toBe(true)
      expect(wpsAPI.value).not.toBeNull()
      expect(wpsAPI.value?.ActiveDocument.Content.Text).toBe('模拟文档全文内容')
    })
  })

  describe('WPS API 不可用时', () => {
    afterEach(() => {
      removeMockWPS()
    })

    it('应该设置 isWPSAvailable = false', () => {
      removeMockWPS()
      const { isWPSAvailable, wpsAPI } = withSetup(useWPSDetection)

      expect(isWPSAvailable.value).toBe(false)
      expect(wpsAPI.value).toBeNull()
    })
  })
})

// ── useWPSSelection ──────────────────────────────────────

describe('useWPSSelection', () => {
  describe('getSelectionInfo()', () => {
    afterEach(() => {
      removeMockWPS()
    })

    it('应该返回完整的 SelectionInfo（含真实偏移量）', () => {
      createMockWPSEnvironment({
        selectionText: '测试选区',
        selectionStart: 100,
        selectionEnd: 150,
      })

      const { getSelectionInfo } = withSetup(useWPSSelection)
      const info = getSelectionInfo()

      expect(info).not.toBeNull()
      expect(info!.text).toBe('测试选区')
      expect(info!.start).toBe(100)
      expect(info!.end).toBe(150)
      expect(info!.source).toBe('range')
    })

    it('当 Range.Text 为空时应 fallback 到 Selection.Text', () => {
      createMockWPSEnvironment({
        selectionText: 'Selection 文本',
        selectionStart: 10,
        selectionEnd: 20,
        rangeText: '', // range 为空 → fallback
      })

      const { getSelectionInfo } = withSetup(useWPSSelection)
      const info = getSelectionInfo()

      expect(info).not.toBeNull()
      expect(info!.text).toBe('Selection 文本')
      expect(info!.source).toBe('selection')
      expect(info!.start).toBe(10)
      expect(info!.end).toBe(20)
    })

    it('当选区文本为空时应返回 null', () => {
      createMockWPSEnvironment({
        selectionText: '',
        rangeText: '',
      })

      const { getSelectionInfo } = withSetup(useWPSSelection)
      const info = getSelectionInfo()

      expect(info).toBeNull()
    })

    it('当 WPS API 不可用时应返回 null', () => {
      removeMockWPS()
      const { getSelectionInfo } = withSetup(useWPSSelection)

      const info = getSelectionInfo()
      expect(info).toBeNull()
    })
  })

  describe('getDocumentContent()', () => {
    afterEach(() => {
      removeMockWPS()
    })

    it('应该返回文档全文', () => {
      createMockWPSEnvironment({
        documentText: '这是完整的论文文档内容。\n包含多行文本。',
      })

      const { getDocumentContent } = withSetup(useWPSSelection)
      const content = getDocumentContent()

      expect(content).toBe('这是完整的论文文档内容。\n包含多行文本。')
    })

    it('当文档为空时应返回空字符串', () => {
      createMockWPSEnvironment({ documentText: '' })

      const { getDocumentContent } = withSetup(useWPSSelection)
      const content = getDocumentContent()

      expect(content).toBe('')
    })

    it('当 WPS API 不可用时应返回空字符串', () => {
      removeMockWPS()
      const { getDocumentContent } = withSetup(useWPSSelection)

      const content = getDocumentContent()
      expect(content).toBe('')
    })
  })

  describe('getSelectedText() 向后兼容', () => {
    afterEach(() => {
      removeMockWPS()
    })

    it('应该仍然返回选区的纯文本', () => {
      createMockWPSEnvironment({
        selectionText: '旧 API 选区',
        selectionStart: 5,
        selectionEnd: 12,
      })

      const { getSelectedText } = withSetup(useWPSSelection)
      const text = getSelectedText()

      expect(text).toBe('旧 API 选区')
    })
  })
})

// ── useWPSSelectionChange ────────────────────────────────

describe('useWPSSelectionChange', () => {
  let mock: MockWPSEnvironment

  beforeEach(() => {
    vi.useFakeTimers()
    mock = createMockWPSEnvironment({
      selectionText: '初始选区',
      selectionStart: 0,
      selectionEnd: 4,
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    removeMockWPS()
  })

  function setupSelectionChange() {
    const calls: SelectionInfo[] = []
    const { bindHandler, startRebindWatch, stopRebindWatch } = withSetup(() =>
      useWPSSelectionChange((info) => {
        calls.push(info)
      }),
    )

    // 手动绑定（onMounted 在 withSetup 中已触发，但 bindHandler 需手动调用）
    bindHandler()

    return { calls, bindHandler, startRebindWatch, stopRebindWatch }
  }

  it('应该在选区变化后 300ms 触发回调', () => {
    const { calls } = setupSelectionChange()

    mock.fireSelectionChange()

    // 还没到 300ms，不应该触发
    vi.advanceTimersByTime(200)
    expect(calls.length).toBe(0)

    // 到达 300ms，应该触发
    vi.advanceTimersByTime(100)
    expect(calls.length).toBe(1)
    expect(calls[0].text).toBe('初始选区')
    expect(calls[0].start).toBe(0)
    expect(calls[0].end).toBe(4)
  })

  it('快速连续选区变化应该只触发最后一次（debounce）', () => {
    const { calls } = setupSelectionChange()

    // 快速连续触发 3 次，每次重置 timer
    mock.fireSelectionChange()
    vi.advanceTimersByTime(100)
    mock.setSelection('第二次选区', 10, 16)
    mock.fireSelectionChange()
    vi.advanceTimersByTime(100)
    mock.setSelection('第三次选区', 20, 26)
    mock.fireSelectionChange()

    // 还没到 debounce 结束
    expect(calls.length).toBe(0)

    // 到达 300ms（从最后一次触发算起）
    vi.advanceTimersByTime(300)
    expect(calls.length).toBe(1)
    expect(calls[0].text).toBe('第三次选区')
    expect(calls[0].start).toBe(20)
    expect(calls[0].end).toBe(26)
  })

  it('rebind watch 应该每 2s 重新绑定而不会报错', () => {
    const { startRebindWatch, stopRebindWatch } = setupSelectionChange()

    startRebindWatch()

    // 2s 后应该触发重绑
    vi.advanceTimersByTime(2000)

    // 不应报错
    stopRebindWatch()
  })
})
