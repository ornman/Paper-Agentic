import { apiRequest } from './api-client'

export interface ContextState {
  session_id: string
  written_context: string
  selection: string
}

export async function updateWrittenContext(sessionId: string, content: string): Promise<void> {
  await apiRequest('/api/v1/assistant/written-context', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, content }),
  })
}

export async function getWrittenContext(sessionId: string): Promise<ContextState> {
  return apiRequest(`/api/v1/assistant/written-context/${encodeURIComponent(sessionId)}`)
}

export async function updateSelection(
  sessionId: string,
  selection: string,
  start?: number,
  end?: number,
): Promise<void> {
  await apiRequest('/api/v1/assistant/selection', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, selection, start, end }),
  })
}

export async function getSelection(sessionId: string): Promise<ContextState> {
  return apiRequest(`/api/v1/assistant/selection/${encodeURIComponent(sessionId)}`)
}
