// 会话消息：描述单会话消息流中的最小消息结构。
// Task 1 先只定义角色、文本与时间，来源卡片等能力后续再补。
export interface ConversationMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  createdAt: string
}
