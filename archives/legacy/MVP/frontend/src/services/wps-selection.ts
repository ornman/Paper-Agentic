interface WpsSelectionLike {
  Text?: unknown
  Range?: {
    Text?: unknown
  } | null
}

interface WpsWindowLike {
  Selection?: WpsSelectionLike | null
  SelectionChange?: ((selection: WpsSelectionLike) => void) | null
}

interface WpsApplicationLike {
  ActiveWindow?: WpsWindowLike | null
}

interface WpsApiLike {
  WpsApplication?: () => WpsApplicationLike | null | undefined
}

function resolveWpsApi(): WpsApiLike | undefined {
  const runtime = globalThis as typeof globalThis & { wps?: WpsApiLike }
  return runtime.wps
}

function normalizeString(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

export interface SelectionSnapshot {
  text: string
  updatedAt: string | null
}

function readSelectionSnapshot(): SelectionSnapshot {
  try {
    const wpsApi = resolveWpsApi()
    const app = wpsApi?.WpsApplication?.()
    const selection = app?.ActiveWindow?.Selection
    const text = normalizeString(selection?.Text) || normalizeString(selection?.Range?.Text)

    return {
      text,
      updatedAt: text ? new Date().toISOString() : null,
    }
  } catch {
    return {
      text: '',
      updatedAt: null,
    }
  }
}

export interface SelectionWatcher {
  start: (onChange: (snapshot: SelectionSnapshot) => void) => void
  stop: () => void
  getSnapshot: () => SelectionSnapshot
}

/**
 * 选区监听策略：
 * 1) 优先用 WPS 的 SelectionChange 事件，实时更新。
 * 2) 如果宿主不支持事件或异常，则回退到 5 秒轮询（和正文轮询同周期）。
 */
export function createSelectionWatcher(): SelectionWatcher {
  let timer: ReturnType<typeof setInterval> | null = null
  let handler: ((selection: unknown) => void) | null = null
  let latestSnapshot: SelectionSnapshot = {
    text: '',
    updatedAt: null,
  }

  function emitIfChanged(onChange: (snapshot: SelectionSnapshot) => void) {
    const nextSnapshot = readSelectionSnapshot()
    if (nextSnapshot.text === latestSnapshot.text && nextSnapshot.updatedAt === latestSnapshot.updatedAt) {
      return
    }

    latestSnapshot = nextSnapshot
    onChange({ ...latestSnapshot })
  }

  function stop() {
    const wpsApi = resolveWpsApi()

    if (handler) {
      try {
        const app = wpsApi?.WpsApplication?.()
        if (app?.ActiveWindow) {
          app.ActiveWindow.SelectionChange = null
        }
      } catch {
        // ignore
      }
      handler = null
    }

    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  function start(onChange: (snapshot: SelectionSnapshot) => void) {
    stop()

    const wpsApi = resolveWpsApi()

    // 选区现在以主动轮询为主，保证和用户视图保持同步。
    // 事件监听只作为增量优化，不能再当作唯一数据来源。
    timer = setInterval(() => {
      emitIfChanged(onChange)
    }, 350)

    latestSnapshot = readSelectionSnapshot()
    onChange({ ...latestSnapshot })

    try {
      const app = wpsApi?.WpsApplication?.()
      if (app?.ActiveWindow) {
        handler = () => {
          emitIfChanged(onChange)
        }

        app.ActiveWindow.SelectionChange = handler as unknown as (selection: WpsSelectionLike) => void
      }
    } catch {
      // ignore
    }
  }

  return {
    start,
    stop,
    getSnapshot() {
      return { ...latestSnapshot }
    },
  }
}
