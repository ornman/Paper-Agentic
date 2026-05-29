import { buildApiUrl, ApiClientError } from './api-client'

export interface ContextState {
  session_id: string
  written_context: string
  selection: string
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(buildApiUrl(path), init)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new ApiClientError(body.message || body.detail || `HTTP ${res.status}`, res.status)
  }
  return body as T
}

export async function updateWrittenContext(sessionId: string, content: string): Promise<void> {
  await request('/api/v1/assistant/written-context', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, content }),
  })
}

export async function getWrittenContext(sessionId: string): Promise<ContextState> {
  return request(`/api/v1/assistant/written-context/${encodeURIComponent(sessionId)}`)
}

export async function updateSelection(
  sessionId: string,
  selection: string,
  start?: number,
  end?: number,
): Promise<void> {
  await request('/api/v1/assistant/selection', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, selection, start, end }),
  })
}

export async function getSelection(sessionId: string): Promise<ContextState> {
  return request(`/api/v1/assistant/selection/${encodeURIComponent(sessionId)}`)
}
