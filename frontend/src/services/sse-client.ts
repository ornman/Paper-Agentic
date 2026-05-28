import type { SourceCard } from '../types/source'
import type { ContentBlock } from '../types/content'
import { useLogger } from '../composables/logger'
import { buildApiUrl } from './api-client'

const log = useLogger('api')

export interface AskRequestPayload {
  session_id: string
  prompt: string
  selection?: string
  draft?: string
  paper_ids?: string[] | null
  enable_rag?: boolean
  /** 选中的模型名称 */
  model?: string
  /** 是否开启思考模式 */
  thinking?: boolean
}

export interface AskStreamHandlers {
  /** 思考过程文本 */
  onThinking?: (thinkingText: string, timeMs: number) => void
  /** 块级内容：paragraph / heading 等 */
  onBlock?: (block: ContentBlock) => void
  /** 所有来源列表（SSE 最后一次性发送） */
  onSources?: (sources: SourceCard[]) => void
  /** 流结束 */
  onDone?: () => void
  /** 错误事件 */
  onErrorEvent?: (message: string) => void
}

interface ParsedSseFrame {
  event: string
  data: unknown
}

const ASK_ENDPOINT = '/api/v1/query'

function parseJsonSafely(rawText: string): unknown {
  try {
    return JSON.parse(rawText)
  } catch {
    return rawText
  }
}

function parseSseFrame(frameText: string): ParsedSseFrame | null {
  const lines = frameText
    .split('\n')
    .map((line) => line.replace(/\r$/, ''))
    .filter((line) => !line.startsWith(':'))

  if (lines.length === 0) {
    return null
  }

  let eventName = 'message'
  const dataLines: string[] = []

  for (const line of lines) {
    if (line.startsWith('event:')) {
      eventName = line.slice('event:'.length).trim()
      continue
    }

    if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trimStart())
    }
  }

  return {
    event: eventName,
    data: parseJsonSafely(dataLines.join('\n')),
  }
}

/** 解析 thinking 事件数据 */
function parseThinkingPayload(payload: unknown): { text: string; timeMs: number } | null {
  if (typeof payload === 'string') {
    return { text: payload, timeMs: 0 }
  }
  if (payload && typeof payload === 'object') {
    const record = payload as Record<string, unknown>
    const text = typeof record.text === 'string' ? record.text
      : typeof record.thinking === 'string' ? record.thinking
      : typeof record.content === 'string' ? record.content
      : ''
    const timeMs = typeof record.time_ms === 'number' ? record.time_ms
      : typeof record.duration_ms === 'number' ? record.duration_ms
      : 0
    return { text, timeMs }
  }
  return null
}

/** 解析 block 事件数据 */
function parseBlockPayload(payload: unknown): ContentBlock | null {
  if (payload && typeof payload === 'object') {
    const record = payload as Record<string, unknown>
    if (typeof record.type === 'string') {
      return record as unknown as ContentBlock
    }
  }
  return null
}

/** 解析 sources 事件数据 */
function parseSourcesPayload(payload: unknown): SourceCard[] {
  if (Array.isArray(payload)) {
    return payload as SourceCard[]
  }
  return []
}

export async function postAskStream(
  payload: AskRequestPayload,
  handlers: AskStreamHandlers,
): Promise<void> {
  const url = buildApiUrl(ASK_ENDPOINT)

  const controller = new AbortController()
  const timeoutId = setTimeout(() => {
    log.warn('SSE 请求超时，主动中断')
    controller.abort()
  }, 120_000)

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })

    clearTimeout(timeoutId)

    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}`
      try {
        const errorBody = await response.json()
        if (typeof errorBody.detail === 'string') {
          errorMessage = errorBody.detail
        } else if (typeof errorBody.message === 'string') {
          errorMessage = errorBody.message
        }
      } catch {
        // 无法解析错误体，用默认 message
      }
      handlers.onErrorEvent?.(errorMessage)
      return
    }

    const reader = response.body?.getReader()
    if (!reader) {
      handlers.onErrorEvent?.('浏览器不支持流式读取')
      return
    }

    const decoder = new TextDecoder()
    let buffer = ''
    let reading = true

    while (reading) {
      const { done, value } = await reader.read()
      if (done) {
        reading = false
        break
      }

      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''

      for (const part of parts) {
        const frame = parseSseFrame(part)
        if (!frame) continue

        switch (frame.event) {
          case 'thinking': {
            const parsed = parseThinkingPayload(frame.data)
            if (parsed) {
              handlers.onThinking?.(parsed.text, parsed.timeMs)
            }
            break
          }
          case 'block': {
            const parsed = parseBlockPayload(frame.data)
            if (parsed) {
              handlers.onBlock?.(parsed)
            }
            break
          }
          case 'sources': {
            const parsed = parseSourcesPayload(frame.data)
            handlers.onSources?.(parsed)
            break
          }
          case 'done': {
            handlers.onDone?.()
            break
          }
          case 'error': {
            const message = typeof frame.data === 'string'
              ? frame.data
              : (frame.data as Record<string, unknown>)?.message as string | undefined
              ?? '未知错误'
            handlers.onErrorEvent?.(message)
            break
          }
          // 兼容旧格式：message 事件降级为单块渲染
          case 'message': {
            if (typeof frame.data === 'string' && frame.data) {
              handlers.onBlock?.({ type: 'paragraph', text: frame.data })
            }
            break
          }
        }
      }
    }

    // 缓冲区剩余内容
    if (buffer.trim()) {
      const frame = parseSseFrame(buffer)
      if (frame && frame.event === 'done') {
        handlers.onDone?.()
      }
    }
  } catch (error: unknown) {
    clearTimeout(timeoutId)
    if (error instanceof DOMException && error.name === 'AbortError') {
      handlers.onErrorEvent?.('请求超时')
    } else {
      const message = error instanceof Error ? error.message : String(error)
      log.error('SSE 请求失败', error)
      handlers.onErrorEvent?.(message)
    }
  }
}
