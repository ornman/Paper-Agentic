// 知识库摘要：描述知识库入口条在前端中最小需要展示的信息。
// 后续任务再扩展导入状态、错误详情与统计字段。
export interface LibrarySummary {
  totalDocuments: number
  status: 'unavailable' | 'empty' | 'ready' | 'importing' | 'error'
  activeDocumentName: string | null
}
