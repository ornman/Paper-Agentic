export interface ApiResponseEnvelope<TData> {
  code: number
  data: TData | null
  message: string
}

export class ApiClientError extends Error {
  readonly statusCode: number | null

  constructor(message: string, statusCode: number | null = null) {
    super(message)
    this.name = 'ApiClientError'
    this.statusCode = statusCode
  }
}

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000'
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

export function buildApiUrl(pathname: string): string {
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

async function requestJson<TData>(pathname: string, init?: RequestInit): Promise<ApiResponseEnvelope<TData>> {
  const response = await fetch(buildApiUrl(pathname), init)
  const payload = await readJsonSafely(response)

  if (!response.ok) {
    throw new ApiClientError(extractErrorMessage(payload, `HTTP ${response.status}`), response.status)
  }

  return payload as ApiResponseEnvelope<TData>
}

export async function requestJsonData<TData>(pathname: string, init?: RequestInit): Promise<TData> {
  const response = await requestJson<TData>(pathname, init)
  return response.data as TData
}

export async function fetchHealthCheck(): Promise<{ status: string }> {
  const response = await requestJson<{ status: string }>('/api/v1/health', undefined)
  return { status: response.data?.status ?? 'ok' }
}

export async function postJson<TData>(pathname: string, body: unknown): Promise<TData> {
  const response = await fetch(buildApiUrl(pathname), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw new ApiClientError(`HTTP ${response.status}`, response.status)
  }
  return response.json() as Promise<TData>
}
