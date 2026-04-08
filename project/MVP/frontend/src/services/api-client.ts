export interface ApiResponseEnvelope<TData> {
  code: number
  data: TData | null
  message: string
}

export interface LibraryDocumentRecord {
  document_id: string
  title: string
  file_path: string
  index_mode: string
  status: string
  error_stage?: string | null
  error_message?: string | null
}

export interface LibraryImportPayload {
  file_path: string
  index_mode: 'brute'
}

/**
 * API 客户端错误。
 *
 * 这里额外保留 HTTP 状态码，原因是 store 层需要根据“请求失败类型”
 * 决定界面语义：
 * 1. 读取失败 -> unavailable / 读取失败
 * 2. 路径非法 -> 输入有误
 * 3. 其他导入失败 -> 中性失败文案
 */
export class ApiClientError extends Error {
  readonly statusCode: number | null

  constructor(message: string, statusCode: number | null = null) {
    super(message)
    this.name = 'ApiClientError'
    this.statusCode = statusCode
  }
}

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000'
const LIBRARY_DOCUMENTS_ENDPOINT = '/api/v1/library/documents'
const LIBRARY_IMPORT_ENDPOINT = '/api/v1/library/import'
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

/**
 * 规范化并校验 API 基地址。
 *
 * 这里要显式做本机白名单收口，原因不是“配置优雅”，而是“数据边界安全”：
 * 当前导入接口会携带本地 PDF 路径，一旦 base URL 被误配到外部主机，
 * 本地路径就可能被发出机器。
 *
 * 允许范围只保留两类：
 * 1. `/`：但仅当当前运行页面本身就是本机 http(s) 回环地址
 * 2. `http(s)://127.0.0.1|localhost|[::1](:port)`：本机回环地址
 *
 * 其他情况一律回退到默认本机地址，而不是“尽量相信配置”。
 */
function normalizeConfiguredApiBaseUrl(configuredBaseUrl: string): string {
  if (configuredBaseUrl === '/') {
    return normalizeCurrentRuntimeOrigin() ?? DEFAULT_API_BASE_URL
  }

  // `//host` 是协议相对地址。
  // 它会偷偷继承当前页面协议，本质上仍然是“把请求发到外部主机”，因此必须直接拒绝。
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

/**
 * 读取并规范化 API 基地址。
 *
 * 约束原因：
 * 1. 当前前端工程没有 dev proxy，不能继续假定前后端天然同源；
 * 2. 测试里会动态 stub 环境变量，因此这里必须按“调用时”读取，
 *    不能在模块加载时就把值锁死；
 * 3. 第一版给出一个本地 FastAPI 默认地址，保证开发/测试开箱可用；
 * 4. 环境变量只是输入，不是信任源，必须经过 allowlist 校验后才能使用。
 */
function resolveApiBaseUrl(): string {
  const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim()

  if (!configuredBaseUrl) {
    return DEFAULT_API_BASE_URL
  }

  return normalizeConfiguredApiBaseUrl(configuredBaseUrl)
}

/**
 * 拼接完整 API URL。
 *
 * 这里显式处理 `/`，避免用户真的想走同源代理时拼出 `//api/...` 这种错误地址。
 */
function buildApiUrl(pathname: string): string {
  const apiBaseUrl = resolveApiBaseUrl()
  const normalizedPathname = pathname.startsWith('/') ? pathname : `/${pathname}`

  if (apiBaseUrl === '/') {
    return normalizedPathname
  }

  return `${apiBaseUrl}${normalizedPathname}`
}

/**
 * 安全读取 JSON。
 *
 * 后端正常情况下会返回统一的 JSON 包装；
 * 但为了避免异常响应体直接让前端二次报错，这里先做最小兜底。
 */
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

/**
 * 从未知响应体里尽量提取可读错误信息。
 *
 * 这里不把后端细节直接暴露给 UI，
 * 但服务层仍然需要保留一个尽量可读的 message，便于 store 再做语义映射。
 */
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

/**
 * 统一请求 JSON API。
 *
 * 设计重点：
 * 1. 保持前端 API 层只关心 HTTP 与统一响应包；
 * 2. 不在这里写 UI 文案，避免服务层和界面文案强耦合；
 * 3. GET 明确传入 undefined，便于测试锁死当前调用契约；
 * 4. 出错时抛出带状态码的错误，给 store 做语义分流。
 */
async function requestJson<TData>(pathname: string, init?: RequestInit): Promise<ApiResponseEnvelope<TData>> {
  const response = await fetch(buildApiUrl(pathname), init)
  const payload = await readJsonSafely(response)

  if (!response.ok) {
    throw new ApiClientError(extractErrorMessage(payload, `HTTP ${response.status}`), response.status)
  }

  return payload as ApiResponseEnvelope<TData>
}

/**
 * 读取知识库文档列表。
 */
export async function fetchLibraryDocuments(): Promise<LibraryDocumentRecord[]> {
  const response = await requestJson<LibraryDocumentRecord[]>(LIBRARY_DOCUMENTS_ENDPOINT, undefined)
  return Array.isArray(response.data) ? response.data.map((item) => ({ ...item })) : []
}

/**
 * 提交 PDF 路径导入请求。
 *
 * 第一版索引模式固定为 brute，
 * 这里直接在 API 层锁死，避免页面层自己拼装魔法字符串。
 */
export async function importLibraryPdf(filePath: string): Promise<LibraryDocumentRecord> {
  const payload: LibraryImportPayload = {
    file_path: filePath,
    index_mode: 'brute',
  }

  const response = await requestJson<LibraryDocumentRecord>(LIBRARY_IMPORT_ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  return {
    ...(response.data as LibraryDocumentRecord),
  }
}
