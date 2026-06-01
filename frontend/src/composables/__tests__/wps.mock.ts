/**
 * WPS 宿主环境 Mock 层
 *
 * 模拟 window.wps 和 WPSApplication，用于单元测试。
 * 所有 mock 行为可配置，默认返回合理值。
 */

export interface MockWPSOverrides {
  documentText?: string
  selectionText?: string
  selectionStart?: number
  selectionEnd?: number
  /** 默认等于 selectionText，显式设置可覆盖（设为 '' 模拟无 range 场景） */
  rangeText?: string
}

export interface MockWPSEnvironment {
  application: WPSApplication
  /** SelectionChange 被赋值时记录的回调列表 */
  changeHandlers: Array<((selection: unknown) => void) | null>
  /** 模拟选区变化（触发已注册的 SelectionChange 回调） */
  fireSelectionChange: () => void
  /** 更新 mock 选区文本，rangeText 默认跟随 text */
  setSelection: (text: string, start?: number, end?: number, rangeText?: string) => void
  /** 更新 mock 文档全文 */
  setDocumentText: (text: string) => void
}

interface WPSApplication {
  ActiveDocument: {
    Content: {
      Text: string
    }
  }
  ActiveWindow: {
    Selection: {
      Text: string
      Start: number
      End: number
      Range: {
        Text: string
      }
    }
    SelectionChange: ((selection: unknown) => void) | null
  }
}

/**
 * 创建完整的 WPS mock 环境（包括 window.wps）
 * 返回 mock 对象引用，测试中可以修改其属性来模拟不同场景
 */
export function createMockWPSEnvironment(overrides?: MockWPSOverrides): MockWPSEnvironment {
  const changeHandlers: Array<((selection: unknown) => void) | null> = []

  const selText = overrides?.selectionText ?? '模拟选区文本'
  // rangeText 默认继承 selectionText，除非显式指定
  const rangeText = overrides?.rangeText !== undefined ? overrides.rangeText : selText

  const selectionState = {
    text: selText,
    start: overrides?.selectionStart ?? 42,
    end: overrides?.selectionEnd ?? 56,
    rangeText,
  }

  const docState = {
    text: overrides?.documentText ?? '模拟文档全文内容',
  }

  const application: WPSApplication = {
    ActiveDocument: {
      Content: {
        get Text() {
          return docState.text
        },
      },
    },
    ActiveWindow: {
      Selection: {
        get Text() {
          return selectionState.text
        },
        get Start() {
          return selectionState.start
        },
        get End() {
          return selectionState.end
        },
        Range: {
          get Text() {
            return selectionState.rangeText
          },
        },
      },
      get SelectionChange() {
        return changeHandlers[changeHandlers.length - 1] ?? null
      },
      set SelectionChange(handler: ((selection: unknown) => void) | null) {
        changeHandlers.push(handler)
      },
    },
  }

  const win = (typeof window !== 'undefined' ? window : globalThis) as Record<string, unknown>
  win.wps = {
    WpsApplication: () => application,
  }

  return {
    application,
    changeHandlers,
    fireSelectionChange() {
      for (const handler of changeHandlers) {
        if (handler) handler(application.ActiveWindow.Selection)
      }
    },
    setSelection(text: string, start?: number, end?: number, rText?: string) {
      selectionState.text = text
      if (start !== undefined) selectionState.start = start
      if (end !== undefined) selectionState.end = end
      // rangeText 默认跟随 text，除非显式传入第三个参数
      selectionState.rangeText = rText !== undefined ? rText : text
    },
    setDocumentText(text: string) {
      docState.text = text
    },
  }
}

/**
 * 移除 window.wps（用于测试 API 不可用场景）
 */
export function removeMockWPS() {
  const win = (typeof window !== 'undefined' ? window : globalThis) as Record<string, unknown>
  if (win.wps) {
    delete win.wps
  }
}
