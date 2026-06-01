import { apiRequest } from './api-client'
import type { ConversationSession, ConversationMessage } from '../types/conversation'

export type { ConversationSession, ConversationMessage }

export async function listSessions(): Promise<ConversationSession[]> {
  return apiRequest('/api/v1/conversations')
}

export async function createSession(): Promise<ConversationSession> {
  return apiRequest('/api/v1/conversations', { method: 'POST' })
}

export async function deleteSession(sessionId: string): Promise<void> {
  await apiRequest(`/api/v1/conversations/${encodeURIComponent(sessionId)}`, { method: 'DELETE' })
}

export async function renameSession(sessionId: string, title: string): Promise<ConversationSession> {
  return apiRequest(`/api/v1/conversations/${encodeURIComponent(sessionId)}/title`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
}

export async function getMessages(sessionId: string, limit = 50): Promise<ConversationMessage[]> {
  return apiRequest(`/api/v1/conversations/${encodeURIComponent(sessionId)}/messages?limit=${limit}`)
}
