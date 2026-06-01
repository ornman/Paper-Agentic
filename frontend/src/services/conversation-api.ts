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

export async function getMessages(sessionId: string, limit = 50): Promise<ConversationMessage[]> {
  return apiRequest(`/api/v1/conversations/${encodeURIComponent(sessionId)}/messages?limit=${limit}`)
}
