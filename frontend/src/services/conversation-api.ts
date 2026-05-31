import { buildApiUrl, ApiClientError } from './api-client'

export interface ConversationSession {
  session_id: string
  title: string
  created_at: string
  updated_at: string
}

export interface ConversationMessage {
  session_id: string
  role: string
  content: string
  created_at: string
  sources_json: string | null
  blocks_json: string | null
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(buildApiUrl(path), init)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new ApiClientError(body.message || body.detail || `HTTP ${res.status}`, res.status)
  }
  return body as T
}

export async function listSessions(): Promise<ConversationSession[]> {
  return request('/api/v1/conversations')
}

export async function createSession(): Promise<ConversationSession> {
  return request('/api/v1/conversations', { method: 'POST' })
}

export async function deleteSession(sessionId: string): Promise<void> {
  await request(`/api/v1/conversations/${encodeURIComponent(sessionId)}`, { method: 'DELETE' })
}

export async function getMessages(sessionId: string, limit = 50): Promise<ConversationMessage[]> {
  return request(`/api/v1/conversations/${encodeURIComponent(sessionId)}/messages?limit=${limit}`)
}
