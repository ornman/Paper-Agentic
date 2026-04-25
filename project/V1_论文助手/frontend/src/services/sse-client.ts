import type { SourceCard } from '../types/source'
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
}

export interface AskInspirationStreamHandlers {
  onChunk?: (chunkText: string) => void
  onSources?: (sources: SourceCard[]) => void
  onDone?: () => void
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

function normalizeChunkText(payload: unknown): string {
  if (typeof payload === 'string') {
    return payload
  }

  if (!payload || typeof payload !== 'object') {
    return ''
  }

  const record = payload as Record<string, unknown>
  const candidateKeys = ['text', 'chunk', 'content', 'answer', 'delta']

  for (const key of candidateKeys) {
    const value = record[key]
    if (typeof value === 'string' && value) {
      return value
    }
  }

  return ''
}

function resolveSourceTitle(record: Record<string, unknown>, index: number): string {
  if (typeof record.title === 'string' && record.title) {
    return record.title
  }

  if (typeof record.document === 'string' && record.document) {
    return record.document
  }

  if (typeof record.section === 'string' && record.section) {
    return record.section
  }

  return `来源 ${index + 1}`
}

function normalizeSourceCard(input: unknown, index: number): SourceCard | null {
  if (!input || typeof input !== 'object') {
    return null
  }

  const record = input as Record<string, unknown>
  const rawId = record.id ?? record.paper_id
  const id =
    (typeof rawId === 'string' && rawId) || typeof rawId === 'number'
      ? String(rawId)
      : `source-${index + 1}`

  const title = resolveSourceTitle(record, index)

  return {
    id,
    paper_id: typeof record.paper_id === 'string' ? record.paper_id : undefined,
    title,
    page: typeof record.page === 'number' ? record.page : undefined,
    section: typeof record.section === 'string' ? record.section : undefined,
    file_path: typeof record.file_path === 'string' ? record.file_path : undefined,
    local_path: typeof record.local_path === 'string' ? record.local_path : undefined,
    content: typeof record.content === 'string' ? record.content : '',
  }
}

function normalizeSources(payload: unknown): SourceCard[] {
  const rawSources = Array.isArray(payload)
    ? payload
    : payload && typeof payload === 'object' && Array.isArray((payload as { sources?: unknown }).sources)
      ? ((payload as { sources: unknown[] }).sources ?? [])
      : []

  return rawSources
    .map((item, index) => normalizeSourceCard(item, index))
    .filter((item): item is SourceCard => item !== null)
}

async function processFrameText(
  frameText: string,
  handlers: AskInspirationStreamHandlers,
  onTerminal?: () => Promise<void> | void,
): Promise<boolean> {
  const parsedFrame = parseSseFrame(frameText)
  if (!parsedFrame) {
    return false
  }

  switch (parsedFrame.event) {
    case 'chunk': {
      const chunkText = normalizeChunkText(parsedFrame.data)
      if (chunkText) {
        handlers.onChunk?.(chunkText)
      }
      return false
    }
    case 'sources':
    case 'metadata': {
      const data = parsedFrame.data as Record<string, unknown> | null
      const rawSources = data && typeof data === 'object'
        ? (data as Record<string, unknown>).sources ?? parsedFrame.data
        : parsedFrame.data
      handlers.onSources?.(normalizeSources(rawSources))
      return false
    }
    case 'done': {
      handlers.onDone?.()
      await onTerminal?.()
      return true
    }
    case 'error': {
      const message = typeof parsedFrame.data === 'string' ? parsedFrame.data : '请求失败'
      handlers.onErrorEvent?.(message)
      await onTerminal?.()
      return true
    }
    default:
      return false
  }
}

async function drainSseBuffer(
  state: { buffer: string; terminal: boolean },
  handlers: AskInspirationStreamHandlers,
  flushRemaining = false,
  onTerminal?: () => Promise<void> | void,
): Promise<void> {
  state.buffer = state.buffer.replace(/\r\n/g, '\n')

  let separatorIndex = state.buffer.indexOf('\n\n')
  while (separatorIndex >= 0 && !state.terminal) {
    const frameText = state.buffer.slice(0, separatorIndex)
    state.buffer = state.buffer.slice(separatorIndex + 2)
    state.terminal = await processFrameText(frameText, handlers, onTerminal)
    separatorIndex = state.buffer.indexOf('\n\n')
  }

  if (flushRemaining && state.buffer.trim() && !state.terminal) {
    state.terminal = await processFrameText(state.buffer, handlers, onTerminal)
    state.buffer = ''
  }
}

async function readFetchSseStream(
  body: ReadableStream<Uint8Array>,
  handlers: AskInspirationStreamHandlers,
): Promise<void> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  const state = { buffer: '', terminal: false }

  while (!state.terminal) {
    const { done, value } = await reader.read()

    if (done) {
      state.buffer += decoder.decode()
      await drainSseBuffer(state, handlers, true)
      break
    }

    state.buffer += decoder.decode(value, { stream: true })
    await drainSseBuffer(state, handlers, false, async () => {
      await reader.cancel()
    })
  }
}

function readXhrSseStream(
  url: string,
  payload: AskRequestPayload,
  handlers: AskInspirationStreamHandlers,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    const state = { buffer: '', terminal: false }
    let processedLength = 0

    xhr.open('POST', url, true)
    xhr.setRequestHeader('Content-Type', 'application/json')
    xhr.setRequestHeader('Accept', 'text/event-stream')

    xhr.onprogress = async () => {
      if (state.terminal) {
        return
      }

      const nextChunk = xhr.responseText.slice(processedLength)
      processedLength = xhr.responseText.length
      state.buffer += nextChunk
      await drainSseBuffer(state, handlers, false, () => {
        xhr.abort()
        resolve()
      })
    }

    xhr.onerror = () => {
      if (state.terminal) {
        return
      }
      reject(new Error('网络请求失败'))
    }

    xhr.onload = async () => {
      if (xhr.status < 200 || xhr.status >= 300) {
        let errorMessage = `HTTP ${xhr.status}`
        try {
          const errorData = JSON.parse(xhr.responseText)
          if (typeof errorData.message === 'string') {
            errorMessage = errorData.message
          } else if (typeof errorData.detail === 'string') {
            errorMessage = errorData.detail
          }
        } catch {
          // 忽略解析错误
        }
        reject(new Error(errorMessage))
        return
      }

      if (state.terminal) {
        resolve()
        return
      }

      const nextChunk = xhr.responseText.slice(processedLength)
      processedLength = xhr.responseText.length
      state.buffer += nextChunk
      await drainSseBuffer(state, handlers, true)
      resolve()
    }

    xhr.send(JSON.stringify(payload))
  })
}

function shouldUseXhrStreaming(): boolean {
  return typeof window !== 'undefined' && typeof (window as { wps?: unknown }).wps !== 'undefined'
}

export async function postAskStream(
  payload: AskRequestPayload,
  handlers: AskInspirationStreamHandlers,
): Promise<void> {
  const requestUrl = buildApiUrl(ASK_ENDPOINT)
  log.info('发起问答流请求', {
    sessionId: payload.session_id,
    enableRag: payload.enable_rag,
    paperCount: payload.paper_ids?.length ?? 0,
    transport: shouldUseXhrStreaming() ? 'xhr' : 'fetch',
  })

  if (shouldUseXhrStreaming()) {
    await readXhrSseStream(requestUrl, payload, handlers)
    return
  }

  const response = await fetch(requestUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}`
    try {
      const errorData = await response.json()
      if (typeof errorData.message === 'string') {
        errorMessage = errorData.message
      } else if (typeof errorData.detail === 'string') {
        errorMessage = errorData.detail
      }
    } catch {
      // 忽略解析错误
    }
    throw new Error(errorMessage)
  }

  if (!response.body) {
    throw new Error('SSE 响应体为空')
  }

  await readFetchSseStream(response.body, handlers)
}
