/** 引用注解：关联 sourceId + 在 clean text 中的字符偏移量 */
export interface CitationAnnotation {
  sourceId: string
  offset: number
}

export interface ContentBlock {
  type: 'paragraph' | 'heading' | 'code' | 'list' | 'blockquote' | 'table' | 'divider' | string
  text?: string
  level?: number
  language?: string
  items?: string[]
  ordered?: boolean
  code?: string
  headers?: string[]
  rows?: string[][]
  citations?: CitationAnnotation[]
}
