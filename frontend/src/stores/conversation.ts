import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { SourceCard } from '../types/source'
import type { ContentBlock } from '../types/content'
import { postAskStream } from '../services/sse-client'
import type { AskRequestPayload } from '../services/sse-client'
import { useLogger } from '../composables/logger'
import { useSettingsStore } from './settings'

const log = useLogger('api')

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
}

export type ConversationRecord = UserMessage | AssistantMessage

let messageSequence = 0

function createMessageId(prefix: 'user' | 'assistant'): string {
  messageSequence += 1
  return `${prefix}-${Date.now()}-${messageSequence}`
}

function createSessionId(): string {
  const uuid = globalThis.crypto?.randomUUID?.()
  if (uuid) {
    return `v1-session-${uuid}`
  }
  return `v1-session-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

function cloneSources(sources: SourceCard[]): SourceCard[] {
  return sources.map((source) => ({ ...source }))
}

export const useConversationStore = defineStore('conversation', () => {
  const status = ref<ConversationStatus>('idle')
  const errorMessage = ref<string | null>(null)
  const messages = ref<ConversationRecord[]>([])
  const sessionId = ref<string>(createSessionId())

  // 当前正在流式输出的 assistant 消息
  const activeAssistantId = ref<string | null>(null)

  function getActiveAssistant(): AssistantMessage | null {
    if (!activeAssistantId.value) return null
    return messages.value.find(
      (m) => m.role === 'assistant' && m.id === activeAssistantId.value,
    ) as AssistantMessage | null
  }

  function ensureActiveAssistant(): AssistantMessage {
    const existing = getActiveAssistant()
    if (existing) return existing

    const id = createMessageId('assistant')
    const msg: AssistantMessage = {
      id,
      role: 'assistant',
      createdAt: new Date().toISOString(),
      thinking: '',
      thinkingTimeMs: 0,
      blocks: [],
      sources: [],
    }
    messages.value.push(msg)
    activeAssistantId.value = id
    return msg
  }

  function reset() {
    status.value = 'idle'
    errorMessage.value = null
    messages.value = []
    sessionId.value = createSessionId()
    activeAssistantId.value = null
  }

  /** 发送用户提问并开始 SSE 流 */
  async function sendPrompt(promptContent: {
    session_id: string
    prompt: string
    paper_ids?: string[]
    enable_rag?: boolean
  }) {
    status.value = 'requesting'
    errorMessage.value = null

    // 添加用户消息
    const userMsg: UserMessage = {
      id: createMessageId('user'),
      role: 'user',
      content: promptContent.prompt,
      createdAt: new Date().toISOString(),
    }
    messages.value.push(userMsg)

    // 预创建 assistant 消息
    activeAssistantId.value = null

    const settings = useSettingsStore()

    const payload: AskRequestPayload = {
      session_id: promptContent.session_id,
      prompt: promptContent.prompt,
      paper_ids: promptContent.paper_ids ?? [],
      enable_rag: promptContent.enable_rag ?? (promptContent.paper_ids && promptContent.paper_ids.length > 0),
      model: settings.selectedModel,
      thinking: settings.thinkingEnabled,
    }

    try {
      await postAskStream(payload, {
        onThinking(text, timeMs) {
          if (status.value === 'requesting') {
            status.value = 'thinking'
          }
          const msg = ensureActiveAssistant()
          msg.thinking += text
          msg.thinkingTimeMs = timeMs
        },
        onBlock(block) {
          if (status.value === 'thinking' || status.value === 'requesting') {
            status.value = 'streaming'
          }
          const msg = ensureActiveAssistant()
          msg.blocks.push(block)
        },
        onSources(sources) {
          const msg = getActiveAssistant()
          if (msg) {
            msg.sources = cloneSources(sources)
          }
        },
        onDone() {
          status.value = 'done'
          activeAssistantId.value = null
        },
        onErrorEvent(message) {
          log.error('对话请求失败', new Error(message))
          errorMessage.value = message
          status.value = 'error'
          // 移除非法的空 assistant 消息
          const lastMsg = messages.value[messages.value.length - 1]
          if (lastMsg && lastMsg.role === 'assistant' && (lastMsg as AssistantMessage).blocks.length === 0 && !(lastMsg as AssistantMessage).thinking) {
            messages.value.pop()
          }
          activeAssistantId.value = null
        },
      })
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error)
      log.error('对话请求异常', error)
      errorMessage.value = message
      status.value = 'error'
      activeAssistantId.value = null
    }
  }

  /** 获取当前 assistant 消息的全部来源 */
  function currentSources(): SourceCard[] {
    const lastAssistant = [...messages.value]
      .reverse()
      .find((m): m is AssistantMessage => m.role === 'assistant')
    return lastAssistant?.sources ?? []
  }

  /** 最新一条 assistant 消息 */
  function lastAssistantMessage(): AssistantMessage | null {
    const reversed = [...messages.value].reverse()
    return reversed.find((m): m is AssistantMessage => m.role === 'assistant') ?? null
  }

  return {
    status,
    errorMessage,
    messages,
    sessionId,
    reset,
    sendPrompt,
    currentSources,
    lastAssistantMessage,
  }
})
