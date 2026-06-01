/** 论文条目 */
export interface PaperItem {
  paper_id: string
  title: string
  authors: string
  year: string
  keywords: string[]
  file_path: string
  file_hash: string
  chunk_count: number
  total_pages: number
  import_time: string
  status: string
  library_item_id: string
  kind: string
  file_size: number | null
}

/** 导入启动结果 */
export interface ImportStartResult {
  task_id: string
  status: string
}

/** 导入状态（轮询） */
export interface ImportStatus {
  task_id: string
  paper_id: string | null
  status: string
  current_step: string | null
  error_msg: string | null
  file_name?: string | null
  percent?: number
}

/** 导入进度事件（SSE / 轮询结果投影） */
export interface ImportProgressEvent {
  status: string
  step: string | null
  paper_id: string | null
  error_msg?: string | null
  file_name?: string | null
  percent?: number
}
