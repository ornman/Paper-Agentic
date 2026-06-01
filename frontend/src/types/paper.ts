// ─── Literal Unions ──────────────────────────────────────

/** 论文状态（后端 LibraryItemOut.status） */
export type PaperStatus = 'ready' | 'failed'

/** 导入任务状态（GET /import/status） */
export type ImportTaskStatus = 'queued' | 'running' | 'completed' | 'failed'

/** SSE 进度事件 status 字段 */
export type ImportSseStatus = 'running' | 'stage_done' | 'stage_failed' | 'completed' | 'failed' | 'done'

/** SSE 步骤标识 */
export type ImportStep = 'transforming' | 'vlm_enriching' | 'cleaning' | 'chunking' | 'embedding' | 'indexing'

/** 导入队列项状态（前端 UI 状态） */
export type ImportQueueStatus = 'pending' | 'importing' | 'completed' | 'failed'

// ─── Core Domain Types ──────────────────────────────────

/** 论文条目（前端统一模型） */
export interface PaperItem {
  paper_id: string
  library_item_id: string
  title: string
  authors: string           // 逗号分隔字符串
  year: number | null       // 后端返回 int | null
  keywords: string[]
  file_path: string
  file_hash: string
  chunk_count: number
  total_pages: number
  import_time: string       // ISO 时间戳
  status: PaperStatus
  kind: string              // 文件扩展名，如 ".pdf"
  file_size: number | null
}

/** 导入启动结果（POST /import/start） */
export interface ImportStartResult {
  task_id: string           // 重复时为空字符串
  status: 'queued' | 'duplicate'
}

/** 导入状态（GET /import/status） */
export interface ImportStatus {
  task_id: string
  paper_id: string | null   // 完成后才有
  status: ImportTaskStatus
  current_step: string | null
  error_msg: string | null
  file_name: string | null
  percent: number | null    // ⚠️ 永远为 null，实时百分比走 SSE
}

/** 进度事件（SSE 和轮询共用） */
export type ImportProgressStatus = ImportSseStatus | ImportTaskStatus

/** 进度事件（SSE 和轮询共用投影） */
export interface ImportProgressEvent {
  status: ImportProgressStatus
  step: string | null        // SSE 用 ImportStep，轮询用任意 string
  percent: number
  stage_name?: string | null
  paper_id: string | null
  error_msg: string | null
}

/** 导入队列项（前端 UI 状态） */
export interface ImportQueueItem {
  fileName: string
  file?: File               // 仅 pending 状态持有，用于重试时重新上传
  taskId?: string
  status: ImportQueueStatus
  percent: number
  step: string
  error?: string
}

// ─── Runtime Validation Helpers ──────────────────────────

type RawRecord = Record<string, unknown>

function requiredString(obj: RawRecord, key: string): string {
  const val = obj[key]
  if (typeof val !== 'string' || val.length === 0) {
    throw new Error(`Invalid paper item: missing or empty "${key}"`)
  }
  return val
}

function optionalString(obj: RawRecord, key: string, fallback = ''): string {
  const val = obj[key]
  return typeof val === 'string' ? val : fallback
}

function optionalNumber(obj: RawRecord, key: string, fallback = 0): number {
  const val = obj[key]
  return typeof val === 'number' ? val : fallback
}

function parseStringArray(val: unknown): string[] {
  if (!Array.isArray(val)) return []
  return val.filter((item): item is string => typeof item === 'string')
}

const VALID_PAPER_STATUSES = new Set<string>(['ready', 'failed'])

function parsePaperStatus(val: unknown): PaperStatus {
  if (typeof val === 'string' && VALID_PAPER_STATUSES.has(val)) return val as PaperStatus
  return 'ready'
}

/**
 * 校验并映射后端 LibraryItemOut → 前端 PaperItem。
 * 后端 model_validator 自动填充别名（item_id = paper_id = library_item_id），
 * 这里取 item_id 作为唯一 ID 源。
 */
export function parsePaperItem(raw: unknown): PaperItem {
  if (typeof raw !== 'object' || raw === null) {
    throw new Error('Invalid paper item: expected object')
  }

  const r = raw as RawRecord
  const id = requiredString(r, 'item_id')

  return {
    paper_id: id,
    library_item_id: id,
    title: requiredString(r, 'title'),
    authors: optionalString(r, 'authors'),
    year: typeof r.year === 'number' ? r.year : null,
    keywords: parseStringArray(r.keywords),
    file_path: requiredString(r, 'file_path'),
    file_hash: optionalString(r, 'file_hash'),
    chunk_count: optionalNumber(r, 'chunk_count'),
    total_pages: optionalNumber(r, 'page_count') || optionalNumber(r, 'total_pages'),
    import_time: requiredString(r, 'import_time'),
    status: parsePaperStatus(r.status),
    kind: optionalString(r, 'file_type') || optionalString(r, 'kind'),
    file_size: typeof r.file_size === 'number' ? r.file_size : null,
  }
}

/** 批量解析并校验论文列表 */
export function parsePaperList(raw: unknown): PaperItem[] {
  if (!Array.isArray(raw)) {
    throw new Error('Invalid paper list: expected array')
  }
  return raw.map(parsePaperItem)
}

/** 校验导入启动结果 */
export function parseImportStartResult(raw: unknown): ImportStartResult {
  if (typeof raw !== 'object' || raw === null) {
    throw new Error('Invalid import start result: expected object')
  }
  const r = raw as RawRecord
  return {
    task_id: typeof r.task_id === 'string' ? r.task_id : '',
    status: r.status === 'duplicate' ? 'duplicate' : 'queued',
  }
}

/** 校验导入状态 */
export function parseImportStatus(raw: unknown): ImportStatus {
  if (typeof raw !== 'object' || raw === null) {
    throw new Error('Invalid import status: expected object')
  }
  const r = raw as RawRecord
  return {
    task_id: typeof r.task_id === 'string' ? r.task_id : '',
    paper_id: typeof r.paper_id === 'string' ? r.paper_id : null,
    status: typeof r.status === 'string' ? (r.status as ImportTaskStatus) : 'queued',
    current_step: typeof r.current_step === 'string' ? r.current_step : null,
    error_msg: typeof r.error_msg === 'string' ? r.error_msg : null,
    file_name: typeof r.file_name === 'string' ? r.file_name : null,
    percent: null, // 始终 null，进度走 SSE
  }
}
