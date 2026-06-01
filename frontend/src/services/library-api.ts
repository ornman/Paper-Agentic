// 论文管理 API 客户端

import { buildApiUrl, ApiClientError, apiRequest } from './api-client'
import {
  parsePaperList,
  parseImportStartResult,
  parseImportStatus,
} from '../types/paper'
import type {
  PaperItem,
  ImportStartResult,
  ImportStatus,
} from '../types/paper'

export type { PaperItem, ImportStartResult, ImportStatus }
export type { ImportProgressEvent, ImportQueueItem } from '../types/paper'

// ─── 论文库 CRUD ─────────────────────────────────────────

/** 获取全部论文（不含回收站） */
export async function fetchPapers(): Promise<PaperItem[]> {
  const raw = await apiRequest<unknown>('/api/v1/library/items')
  return parsePaperList(raw)
}

/** 获取单篇论文（含回收站中的） */
export async function fetchPaperById(itemId: string): Promise<PaperItem> {
  const raw = await apiRequest<unknown>(`/api/v1/library/items/${encodeURIComponent(itemId)}`)
  const items = parsePaperList([raw])
  return items[0]
}

/** 软删除（移入回收站） */
export async function deletePaper(paperId: string): Promise<void> {
  await apiRequest(`/api/v1/library/items/${encodeURIComponent(paperId)}`, { method: 'DELETE' })
}

/** 获取回收站列表 */
export async function fetchTrashedPapers(): Promise<PaperItem[]> {
  const raw = await apiRequest<unknown>('/api/v1/library/trash')
  return parsePaperList(raw)
}

/** 从回收站恢复 */
export async function restorePaper(paperId: string): Promise<void> {
  await apiRequest(`/api/v1/library/items/${encodeURIComponent(paperId)}/restore`, { method: 'POST' })
}

/** 永久删除 */
export async function permanentDeletePaper(paperId: string): Promise<void> {
  await apiRequest(`/api/v1/library/items/${encodeURIComponent(paperId)}/permanent`, { method: 'DELETE' })
}

// ─── PDF 阅读 ─────────────────────────────────────────────

/** 构建 PDF 打开 URL */
export function buildPaperOpenUrl(paperId: string): string {
  return buildApiUrl(`/api/v1/papers/${encodeURIComponent(paperId)}/open`)
}

// ─── 导入流程 ─────────────────────────────────────────────

/** 上传 PDF 开始导入 */
export async function startImport(file: File): Promise<ImportStartResult> {
  const form = new FormData()
  form.append('file', file)
  const raw = await apiRequest<unknown>('/api/v1/import/start', { method: 'POST', body: form })
  const result = parseImportStartResult(raw)

  if (result.status === 'duplicate') {
    throw new ApiClientError('该文件已导入过，无需重复导入')
  }
  if (!result.task_id) {
    throw new ApiClientError('导入任务创建失败：缺少 task_id')
  }
  return result
}

/** 查询导入状态（轮询，percent 始终为 null） */
export async function fetchImportStatus(taskId: string): Promise<ImportStatus> {
  const raw = await apiRequest<unknown>(`/api/v1/import/status/${encodeURIComponent(taskId)}`)
  return parseImportStatus(raw)
}

/** 创建 SSE 实时进度流 */
export function createImportStream(taskId: string): EventSource {
  return new EventSource(buildApiUrl(`/api/v1/import/stream/${encodeURIComponent(taskId)}`))
}
