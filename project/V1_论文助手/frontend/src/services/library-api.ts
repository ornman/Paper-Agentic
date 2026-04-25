// 论文管理 API 客户端

import { buildApiUrl, ApiClientError } from './api-client'

export interface PaperItem {
  paper_id: string
  title: string
  authors: string
  file_path: string
  file_hash: string
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
  file_name?: string | null
  percent?: number
}

export interface ImportProgressEvent {
  status: string
  step: string | null
  paper_id: string | null
  error_msg?: string | null
  file_name?: string | null
  percent?: number
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(buildApiUrl(path), init)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = body.detail && typeof body.detail === 'object' ? body.detail.message : undefined
    throw new ApiClientError(body.message || detail || `HTTP ${res.status}`, res.status)
  }
  return body as T
}

export async function fetchPapers(): Promise<{ papers: PaperItem[] }> {
  return request('/api/v1/papers')
}

export function buildPaperOpenUrl(paperId: string): string {
  return buildApiUrl(`/api/v1/papers/${encodeURIComponent(paperId)}/open`)
}

export async function deletePaper(paperId: string): Promise<void> {
  await request(`/api/v1/papers/${encodeURIComponent(paperId)}`, { method: 'DELETE' })
}

export async function startImport(file: File): Promise<ImportStartResult> {
  const form = new FormData()
  form.append('file', file)
  const result = await request<ImportStartResult>('/api/v1/import/start', { method: 'POST', body: form })
  if (!result?.task_id) {
    throw new ApiClientError('导入任务创建失败：缺少 task_id')
  }
  return result
}

export async function fetchImportStatus(taskId: string): Promise<ImportStatus> {
  const result = await request<ImportStatus>(`/api/v1/import/status/${encodeURIComponent(taskId)}`)
  if (!result?.status) {
    throw new ApiClientError('导入状态读取失败：缺少 status')
  }
  return result
}

export function createImportStream(taskId: string): EventSource {
  return new EventSource(buildApiUrl(`/api/v1/import/stream/${encodeURIComponent(taskId)}`))
}
