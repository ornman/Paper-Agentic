import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { SourceCard } from '../types/source'
import { ApiClientError, postJson } from '../services/api-client'
import { postAskStream } from '../services/sse-client'
import type { AskRequestPayload } from '../services/sse-client'
import { useLogger } from '../composables/logger'

const log = useLogger('api')

export type ConversationStatus = 'idle' | 'requesting' | 'streaming' | 'done' | 'error'

export interface ConversationUserActionMessage {
  id: string
  role: 'user'
  kind: 'action' | 'prompt'
  content: string
  createdAt: string
}

export interface ConversationAssistantMessage {
  id: string
  role: 'assistant'
  kind: 'answer'
  content: string
  createdAt: string
  sources?: SourceCard[]
}

export type ConversationRecord = ConversationUserActionMessage | ConversationAssistantMessage

let messageSequence = 0

function createMessageId(prefix: 'user' | 'assistant') {
  messageSequence += 1
  return `${prefix}-${Date.now()}-${messageSequence}`
}

function createSessionId() {
  const uuid = globalThis.crypto?.randomUUID?.()
  if (uuid) {
    return `v1-session-${uuid}`
  }
  return `v1-session-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

function cloneSources(sources: readonly SourceCard[] | undefined): SourceCard[] | undefined {
  if (!sources) return undefined
  return sources.map((source) => ({ ...source }))
}

function extractConversationTitle(messages: Array<{ role: string; content: string }>): string {
  const firstUserMessage = messages.find((message) => message.role === 'user' && message.content.trim())
  if (!firstUserMessage) return ''
  return firstUserMessage.content.trim().slice(0, 20)
}

export const useConversationStore = defineStore('conversation', () => {
  const status = ref<ConversationStatus>('idle')
  const errorMessage = ref<string | null>(null)
  const messages = ref<ConversationRecord[]>([])
  const sessionId = ref<string>(createSessionId())
  const title = ref<string>('AIForScience')

  const activeAssistantMessageId = ref<string | null>(null)
  const pendingAssistantSources = ref<SourceCard[] | null>(null)

  function startRequest() {
    status.value = 'requesting'
    errorMessage.value = null
    activeAssistantMessageId.value = null
    pendingAssistantSources.value = null
  }

  function startStreaming() {
    status.value = 'streaming'
    errorMessage.value = null
  }

  function finishResponse() {
    status.value = 'done'
    errorMessage.value = null
  }

  function markError(message: string) {
    status.value = 'error'
    errorMessage.value = message
  }

  function appendUserActionMessage(payload: { content: string; kind?: 'action' | 'prompt'; createdAt?: string }) {
    const nextMessage: ConversationUserActionMessage = {
      id: createMessageId('user'),
      role: 'user',
      kind: payload.kind ?? 'action',
      content: payload.content,
      createdAt: payload.createdAt ?? new Date().toISOString(),
    }
    messages.value = [...messages.value, nextMessage]
  }

  function createStreamingAssistantMessage(createdAt?: string): string {
    const nextMessage: ConversationAssistantMessage = {
      id: createMessageId('assistant'),
      role: 'assistant',
      kind: 'answer',
      content: '',
      createdAt: createdAt ?? new Date().toISOString(),
      sources: cloneSources(pendingAssistantSources.value ?? undefined),
    }
    activeAssistantMessageId.value = nextMessage.id
    pendingAssistantSources.value = null
    messages.value = [...messages.value, nextMessage]
    return nextMessage.id
  }

  function updateAssistantMessage(
    messageId: string,
    updater: (message: ConversationAssistantMessage) => ConversationAssistantMessage,
  ) {
    messages.value = messages.value.map((message) => {
      if (message.id !== messageId || message.role !== 'assistant') {
        return message
      }
      return updater(message)
    })
  }

  function ensureStreamingAssistantMessage(): string {
    if (activeAssistantMessageId.value) {
      return activeAssistantMessageId.value
    }
    return createStreamingAssistantMessage()
  }

  function appendAssistantChunk(chunkText: string) {
    if (!chunkText) return
    const messageId = ensureStreamingAssistantMessage()
    updateAssistantMessage(messageId, (message) => ({
      ...message,
      content: `${message.content}${chunkText}`,
    }))
  }

  function attachAssistantSources(sources: SourceCard[]) {
    if (sources.length === 0) return
    if (!activeAssistantMessageId.value) {
      pendingAssistantSources.value = cloneSources(sources) ?? null
      return
    }
    const messageId = activeAssistantMessageId.value
    updateAssistantMessage(messageId, (message) => ({
      ...message,
      sources: cloneSources(sources),
    }))
  }

  async function sendPrompt(payload: AskRequestPayload) {
    startRequest()
    const isFirstMessage = messages.value.length === 0
    appendUserActionMessage({
      content: payload.prompt,
      kind: 'prompt',
    })
    log.info('发送问题', {
      sessionId: payload.session_id,
      enableRag: payload.enable_rag,
      paperCount: payload.paper_ids?.length ?? 0,
    })

    try {
      let chunkCount = 0
      await postAskStream(payload, {
        onChunk(chunkText) {
          if (status.value !== 'streaming') {
            startStreaming()
            log.info('收到首个流式分片', { sessionId: payload.session_id })
          }
          chunkCount += 1
          appendAssistantChunk(chunkText)
        },
        onSources(sources) {
          if (status.value !== 'streaming') {
            startStreaming()
          }
          log.info('收到来源数据', { count: sources.length, sessionId: payload.session_id })
          attachAssistantSources(sources)
        },
        onDone() {
          log.info('流式响应完成', { sessionId: payload.session_id, chunkCount })
          finishResponse()
          activeAssistantMessageId.value = null
          pendingAssistantSources.value = null
        },
        onErrorEvent(message) {
          log.warn('流式响应事件错误', { sessionId: payload.session_id, message })
          markError(message)
          activeAssistantMessageId.value = null
          pendingAssistantSources.value = null
        },
      })

      if (status.value !== 'error') {
        finishResponse()
        activeAssistantMessageId.value = null
        pendingAssistantSources.value = null
      }

      if (isFirstMessage && payload.prompt.trim()) {
        try {
          const result = await postJson<{ title: string }>('/api/v1/query/generate-title', {
            message: payload.prompt,
          })
          if (result.title) {
            title.value = result.title
          }
        } catch {
          title.value = payload.prompt.slice(0, 20)
        }
      }
    } catch (error) {
      const message =
        error instanceof ApiClientError || error instanceof Error
          ? error.message
          : '发送失败，请稍后重试'
      log.error('发送问题失败', error, { sessionId: payload.session_id })
      markError(message)
      activeAssistantMessageId.value = null
      pendingAssistantSources.value = null
    }
  }

  function reset() {
    status.value = 'idle'
    errorMessage.value = null
    messages.value = []
    activeAssistantMessageId.value = null
    pendingAssistantSources.value = null
    sessionId.value = createSessionId()
    title.value = 'AIForScience'
  }

  function loadHistory(data: { session_id: string; title?: string; messages: Array<{ role: string; content: string }> }) {
    status.value = 'idle'
    errorMessage.value = null
    activeAssistantMessageId.value = null
    pendingAssistantSources.value = null
    sessionId.value = data.session_id
    title.value = data.title?.trim() || extractConversationTitle(data.messages) || 'AIForScience'

    messages.value = data.messages.map((message) => {
      if (message.role === 'user') {
        return {
          id: createMessageId('user'),
          role: 'user' as const,
          kind: 'prompt' as const,
          content: message.content,
          createdAt: new Date().toISOString(),
        }
      }

      return {
        id: createMessageId('assistant'),
        role: 'assistant' as const,
        kind: 'answer' as const,
        content: message.content,
        createdAt: new Date().toISOString(),
      }
    })
  }

  return {
    status,
    errorMessage,
    messages,
    sessionId,
    title,
    startRequest,
    startStreaming,
    finishResponse,
    markError,
    appendUserActionMessage,
    sendPrompt,
    reset,
    loadHistory,
  }
})
