/** 会话摘要 */
export interface ConversationSession {
  session_id: string
  title: string
  created_at: string
  updated_at: string
}

/** 会话消息（API 返回格式） */
export interface ConversationMessage {
  session_id: string
  role: string
  content: string
  created_at: string
  sources_json: string | null
  blocks_json: string | null
}
