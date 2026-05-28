export interface ContentBlock {
  type: 'paragraph' | 'heading' | 'code' | 'list' | 'blockquote' | string
  text?: string
  level?: number
  language?: string
  items?: string[]
}
