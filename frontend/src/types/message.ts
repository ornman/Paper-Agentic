import type { SourceCard } from './source'
import type { ContentBlock } from './content'

/** 对话状态枚举 */
export type ConversationStatus = 'idle' | 'requesting' | 'thinking' | 'streaming' | 'done' | 'error'

/** 用户消息 */
export interface UserMessage {
  id: string
  role: 'user'
  content: string
  createdAt: string
}

/** AI 消息 */
export interface AssistantMessage {
  id: string
  role: 'assistant'
  createdAt: string
  /** 思考过程文本（可折叠展示） */
  thinking: string
  /** 思考耗时（毫秒） */
  thinkingTimeMs: number
  /** 块级内容 */
  blocks: ContentBlock[]
  /** 本轮引用来源 */
  sources: SourceCard[]
  /** 流式文本（LLM 逐 chunk 到达时累积，blocks 到达后清空） */
  streamingText: string
}

/** 消息联合类型 */
export type ConversationRecord = UserMessage | AssistantMessage
