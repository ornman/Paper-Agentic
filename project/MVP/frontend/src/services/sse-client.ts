import { ApiClientError } from './api-client'
import type { SourceCard } from '../components/conversation/SourceCardList.vue'

/**
 * 后端 `/api/v1/query/ask` 当前真实请求体（AskRequest）。
 *
 * 为什么要在前端单独定义一份？
 * - 前端不能假设后端文档/计划永远正确，必须以真实代码为准；
 * - 显式类型可以在编译期阻止“字段漂移”再次发生；
 * - Task 8 只打通场景 1：用 `context.written_content` 承载 WPS 轮询得到的正文缓存。
 */
export interface AskInspirationRequestPayload {
  session_id: string
  query: string
  context?: {
    written_content?: string
    selected_text?: string
    prompt?: string
  } | null
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
const ASK_ENDPOINT = '/api/v1/query/ask'
const LOCAL_API_HOSTNAME_ALLOWLIST = new Set(['127.0.0.1', 'localhost', '[::1]', '::1'])

function isAllowedLocalHost(hostname: string): boolean {
  return LOCAL_API_HOSTNAME_ALLOWLIST.has(hostname)
}

/**
 * 规范化当前运行时 origin。
 *
 * 这里保持和现有 JSON API 相同的安全边界：
 * 只有当前页面本身就是本机回环地址时，才允许走 `/` 同源相对路径。
 */
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

/**
 * 规范化 API 基地址。
 *
 * ask 接口虽然不发送本地路径，但会发送当前论文正文，
 * 因此仍然应该只允许本机回环地址，避免误把正文发到外部主机。
 */
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

async function readJsonSafely(response: Response | { json?: () => Promise<unknown> }): Promise<unknown> {
  if (typeof response.json !== 'function') {
    return null
  }

  try {
    return await response.json()
  } catch {
    return null
  }
}

function extractErrorMessage(payload: unknown, fallbackMessage: string): string {
  if (typeof payload === 'string' && payload.trim()) {
    return payload
  }

  if (payload && typeof payload === 'object') {
    const record = payload as Record<string, unknown>

    if (typeof record.message === 'string' && record.message.trim()) {
      return record.message
    }

    if (typeof record.detail === 'string' && record.detail.trim()) {
      return record.detail
    }
  }

  return fallbackMessage
}

function parseJsonSafely(rawText: string): unknown {
  try {
    return JSON.parse(rawText)
  } catch {
    return rawText
  }
}

/**
 * 解析单个 SSE 帧。
 *
 * 当前只关心 `event:` 与 `data:` 两类字段，
 * 其他字段先忽略，保持解析器最小可用。
 */
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

  /**
   * 后端当前真实字段：
   * - id: number
   * - document: 来源文档名
   * - content: 引用片段
   * - page: 页码
   *
   * 前端展示字段仍维持 SourceCard：
   * - title
   * - snippet
   *
   * 因此这里做一层显式映射，而不是要求 UI 组件直接理解后端结构。
   */
  const rawId = record.id
  const id =
    (typeof rawId === 'string' && rawId) || typeof rawId === 'number'
      ? String(rawId)
      : `source-${index + 1}`

  const title =
    typeof record.title === 'string'
      ? record.title
      : typeof record.document === 'string'
        ? record.document
        : ''

  const snippet =
    typeof record.snippet === 'string'
      ? record.snippet
      : typeof record.content === 'string'
        ? record.content
        : ''

  const page = typeof record.page === 'number' ? record.page : undefined

  // 来源卡片至少要有标题或片段中的一个，
  // 否则渲染出来只会是空壳，没有任何用户价值。
  if (!title && !snippet) {
    return null
  }

  return {
    id,
    title,
    page,
    snippet,
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
      case 'sources': {
        handlers.onSources?.(normalizeSources(parsedFrame.data))
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
        handlers.onErrorEvent?.(extractErrorMessage(parsedFrame.data, '获取灵感失败，请稍后重试'))
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

/**
 * 发起“获取灵感”流式请求。
 *
 * 约束：
 * 1. 固定走 POST `/api/v1/query/ask`
 * 2. 请求接受 SSE 流
 * 3. 只负责网络层和事件解析，不直接碰 Pinia store
 */
export async function postAskInspirationStream(
  payload: AskInspirationRequestPayload,
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
    const errorPayload = await readJsonSafely(response)
    throw new ApiClientError(extractErrorMessage(errorPayload, `HTTP ${response.status}`), response.status)
  }

  if (!response.body) {
    throw new Error('SSE 响应体为空')
  }

  await readSseStream(response.body, handlers)
}
