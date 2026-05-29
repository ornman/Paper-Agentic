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
}
