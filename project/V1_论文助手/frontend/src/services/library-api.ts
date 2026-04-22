// 论文管理 API 客户端

const API_BASE = 'http://127.0.0.1:8000'

export interface PaperItem {
  paper_id: string
  title: string
  authors: string
  chunk_count: number
  total_pages: number
  import_time: string
  status: string
}

export interface ImportStartResult {
  task_id: string
  status: string
}

export interface ImportStatus {
  task_id: string
  paper_id: string | null
  status: string
  current_step: string | null
  error_msg: string | null
}

export interface ImportProgressEvent {
  status: string
  step: string | null
  paper_id: string | null
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.message || body.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function fetchPapers(): Promise<{ papers: PaperItem[] }> {
  return request('/api/v1/papers')
}

export async function deletePaper(paperId: string): Promise<void> {
  await request(`/api/v1/papers/${paperId}`, { method: 'DELETE' })
}

export async function startImport(file: File): Promise<ImportStartResult> {
  const form = new FormData()
  form.append('file', file)
  return request('/api/v1/import/start', { method: 'POST', body: form })
}

export async function fetchImportStatus(taskId: string): Promise<ImportStatus> {
  return request(`/api/v1/import/status/${taskId}`)
}

export function createImportStream(taskId: string): EventSource {
  return new EventSource(`${API_BASE}/api/v1/import/stream/${taskId}`)
}
