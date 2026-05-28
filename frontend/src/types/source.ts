export interface SourceCard {
  id: string
  paper_id?: string
  title: string
  page?: number
  section?: string
  file_path?: string
  local_path?: string
  content?: string
  /** 论文导入时间，用于预览卡片右上角 */
  import_time?: string
}
