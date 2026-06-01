// 论文管理 API 客户端

import { buildApiUrl, ApiClientError } from './api-client'
import type { PaperItem, ImportStartResult, ImportStatus } from '../types/paper'

export type { PaperItem, ImportStartResult, ImportStatus }
export type { ImportProgressEvent } from '../types/paper'

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
  const items = await request<unknown>('/api/v1/library/items')
  return { papers: (items as Record<string, unknown>[]).map(item => ({
    ...item,
    // 后端 LibraryItemOut.item_id 是主键，前端统一映射为 paper_id / library_item_id
    paper_id: (item.item_id as string) || (item.library_item_id as string) || (item.paper_id as string),
    library_item_id: (item.item_id as string) || (item.library_item_id as string),
    year: String(item.year ?? ''),
    keywords: (item.keywords as string[]) ?? [],
    total_pages: (item.page_count as number) ?? (item.total_pages as number) ?? 0,
    chunk_count: (item.chunk_count as number) ?? 0,
    kind: (item.file_type as string) || (item.kind as string) || '',
    file_size: (item.file_size as number | null) ?? null,
  })) as PaperItem[] }
}

export function buildPaperOpenUrl(paperId: string): string {
  return buildApiUrl(`/api/v1/papers/${encodeURIComponent(paperId)}/open`)
}

export async function deletePaper(paperId: string): Promise<void> {
  await request(`/api/v1/library/items/${encodeURIComponent(paperId)}`, { method: 'DELETE' })
}

export async function fetchTrashedPapers(): Promise<PaperItem[]> {
  const items = await request<unknown>('/api/v1/library/trash')
  return (items as Record<string, unknown>[]).map(item => ({
    ...item,
    paper_id: (item.item_id as string) || (item.library_item_id as string) || (item.paper_id as string),
    library_item_id: (item.item_id as string) || (item.library_item_id as string),
    year: String(item.year ?? ''),
    keywords: (item.keywords as string[]) ?? [],
    total_pages: (item.page_count as number) ?? (item.total_pages as number) ?? 0,
    chunk_count: (item.chunk_count as number) ?? 0,
    kind: (item.file_type as string) || (item.kind as string) || '',
    file_size: (item.file_size as number | null) ?? null,
  })) as PaperItem[]
}

export async function restorePaper(paperId: string): Promise<void> {
  await request(`/api/v1/library/items/${encodeURIComponent(paperId)}/restore`, { method: 'POST' })
}

export async function permanentDeletePaper(paperId: string): Promise<void> {
  await request(`/api/v1/library/items/${encodeURIComponent(paperId)}/permanent`, { method: 'DELETE' })
}

export async function retryImport(paperId: string): Promise<ImportStartResult> {
  const result = await request<ImportStartResult>(`/api/v1/library/items/${encodeURIComponent(paperId)}/retry`, { method: 'POST' })
  if (!result?.task_id) {
    throw new ApiClientError('重试导入失败：缺少 task_id')
  }
  return result
}

export async function startImport(file: File): Promise<ImportStartResult> {
  const form = new FormData()
  form.append('file', file)
  const result = await request<ImportStartResult>('/api/v1/import/start', { method: 'POST', body: form })
  if (result?.status === 'duplicate') {
    throw new ApiClientError('该文件已导入过，无需重复导入')
  }
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
