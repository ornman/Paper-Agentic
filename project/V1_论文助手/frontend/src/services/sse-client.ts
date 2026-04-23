import type { SourceCard } from '../components/SourceCardList.vue'

export interface AskRequestPayload {
  session_id: string
  prompt: string
  selection?: string
  draft?: string
  paper_ids?: string[] | null
  enable_rag?: boolean  // 是否启用 RAG 检索，默认 true
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

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000'
const ASK_ENDPOINT = '/api/v1/query'
const LOCAL_API_HOSTNAME_ALLOWLIST = new Set(['127.0.0.1', 'localhost', '[::1]', '::1'])

function isAllowedLocalHost(hostname: string): boolean {
  return LOCAL_API_HOSTNAME_ALLOWLIST.has(hostname)
}

function normalizeCurrentRuntimeOrigin(): string | null {
  if (typeof window === 'undefined' || !window.location) {
    return null
  }

  const { protocol, hostname } = window.location
  if ((protocol !== 'http:' && protocol !== 'https:') || !isAllowedLocalHost(hostname)) {
    return null
  }

  return '/'
}

function normalizeConfiguredApiBaseUrl(configuredBaseUrl: string): string {
  if (configuredBaseUrl === '/') {
    return normalizeCurrentRuntimeOrigin() ?? DEFAULT_API_BASE_URL
  }

  if (configuredBaseUrl.startsWith('//')) {
    return DEFAULT_API_BASE_URL
  }

  let parsedUrl: URL

  try {
    parsedUrl = new URL(configuredBaseUrl)
  } catch {
    return DEFAULT_API_BASE_URL
  }

  const hasAllowedProtocol = parsedUrl.protocol === 'http:' || parsedUrl.protocol === 'https:'
  const hasAllowedHostname = LOCAL_API_HOSTNAME_ALLOWLIST.has(parsedUrl.hostname)
  const isPureOrigin =
    (parsedUrl.pathname === '/' || parsedUrl.pathname === '') &&
    !parsedUrl.search &&
    !parsedUrl.hash &&
    !parsedUrl.username &&
    !parsedUrl.password

  if (!hasAllowedProtocol || !hasAllowedHostname || !isPureOrigin) {
    return DEFAULT_API_BASE_URL
  }

  return parsedUrl.origin
}

function resolveApiBaseUrl(): string {
  const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim()

  if (!configuredBaseUrl) {
    return DEFAULT_API_BASE_URL
  }

  return normalizeConfiguredApiBaseUrl(configuredBaseUrl)
}

function buildApiUrl(pathname: string): string {
  const apiBaseUrl = resolveApiBaseUrl()
  const normalizedPathname = pathname.startsWith('/') ? pathname : `/${pathname}`

  if (apiBaseUrl === '/') {
    return normalizedPathname
  }

  return `${apiBaseUrl}${normalizedPathname}`
}

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

  const title =
    typeof record.title === 'string'
      ? record.title
      : typeof record.document === 'string'
        ? record.document
        : typeof record.section === 'string' && record.section
          ? record.section
          : `来源 ${index + 1}`

  const content = typeof record.content === 'string' ? record.content : ''

  const page = typeof record.page === 'number' ? record.page : undefined
  const section = typeof record.section === 'string' ? record.section : undefined
  const file_path = typeof record.file_path === 'string' ? record.file_path : undefined
  const paper_id = typeof record.paper_id === 'string' ? record.paper_id : undefined

  return {
    id,
    paper_id,
    title,
    page,
    section,
    file_path,
    content,
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

async function readSseStream(
  body: ReadableStream<Uint8Array>,
  handlers: AskInspirationStreamHandlers,
): Promise<void> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let terminalEventReached = false

  async function processFrame(frameText: string) {
    const parsedFrame = parseSseFrame(frameText)
    if (!parsedFrame || terminalEventReached) {
      return
    }

    switch (parsedFrame.event) {
      case 'chunk': {
        const chunkText = normalizeChunkText(parsedFrame.data)
        if (chunkText) {
          handlers.onChunk?.(chunkText)
        }
        return
      }
      case 'sources':
      case 'metadata': {
        const data = parsedFrame.data as Record<string, unknown> | null
        const rawSources = data && typeof data === 'object'
          ? (data as Record<string, unknown>).sources ?? parsedFrame.data
          : parsedFrame.data
        handlers.onSources?.(normalizeSources(rawSources))
        return
      }
      case 'done': {
        terminalEventReached = true
        handlers.onDone?.()
        await reader.cancel()
        return
      }
      case 'error': {
        terminalEventReached = true
        const message = typeof parsedFrame.data === 'string' ? parsedFrame.data : '请求失败'
        handlers.onErrorEvent?.(message)
        await reader.cancel()
        return
      }
      default:
        return
    }
  }

  async function drainBuffer(flushRemaining = false) {
    const normalizedBuffer = buffer.replace(/\r\n/g, '\n')
    buffer = normalizedBuffer

    let separatorIndex = buffer.indexOf('\n\n')
    while (separatorIndex >= 0 && !terminalEventReached) {
      const frameText = buffer.slice(0, separatorIndex)
      buffer = buffer.slice(separatorIndex + 2)
      await processFrame(frameText)
      separatorIndex = buffer.indexOf('\n\n')
    }

    if (flushRemaining && buffer.trim() && !terminalEventReached) {
      await processFrame(buffer)
      buffer = ''
    }
  }

  while (!terminalEventReached) {
    const { done, value } = await reader.read()

    if (done) {
      buffer += decoder.decode()
      await drainBuffer(true)
      break
    }

    buffer += decoder.decode(value, { stream: true })
    await drainBuffer(false)
  }
}

export async function postAskStream(
  payload: AskRequestPayload,
  handlers: AskInspirationStreamHandlers,
): Promise<void> {
  const response = await fetch(buildApiUrl(ASK_ENDPOINT), {
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

  await readSseStream(response.body, handlers)
}
