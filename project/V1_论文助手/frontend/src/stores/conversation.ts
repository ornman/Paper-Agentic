import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { SourceCard } from '../components/SourceCardList.vue'
import { ApiClientError } from '../services/api-client'
import { postAskStream } from '../services/sse-client'
import type { AskRequestPayload } from '../services/sse-client'

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
  return sources.map(s => ({ ...s }))
}

export const useConversationStore = defineStore('conversation', () => {
  const status = ref<ConversationStatus>('idle')
  const errorMessage = ref<string | null>(null)
  const messages = ref<ConversationRecord[]>([])
  const sessionId = ref<string>(createSessionId())

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

  function appendAssistantMessage(payload: {
    content: string
    sources?: SourceCard[]
    createdAt?: string
  }) {
    const nextMessage: ConversationAssistantMessage = {
      id: createMessageId('assistant'),
      role: 'assistant',
      kind: 'answer',
      content: payload.content,
      createdAt: payload.createdAt ?? new Date().toISOString(),
      sources: cloneSources(payload.sources),
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
    appendUserActionMessage({
      content: payload.prompt,
      kind: 'prompt',
    })

    try {
      await postAskStream(payload, {
        onChunk(chunkText) {
          if (status.value !== 'streaming') {
            startStreaming()
          }
          appendAssistantChunk(chunkText)
        },
        onSources(sources) {
          if (status.value !== 'streaming') {
            startStreaming()
          }
          attachAssistantSources(sources)
        },
        onDone() {
          finishResponse()
          activeAssistantMessageId.value = null
          pendingAssistantSources.value = null
        },
        onErrorEvent(message) {
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
    } catch (error) {
      const message =
        error instanceof ApiClientError || error instanceof Error
          ? error.message
          : '发送失败，请稍后重试'
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
  }

  function loadHistory(data: { session_id: string; messages: Array<{ role: string; content: string }> }) {
    status.value = 'idle'
    errorMessage.value = null
    activeAssistantMessageId.value = null
    pendingAssistantSources.value = null
    sessionId.value = data.session_id

    messages.value = data.messages.map((m) => {
      if (m.role === 'user') {
        return {
          id: createMessageId('user'),
          role: 'user' as const,
          kind: 'prompt' as const,
          content: m.content,
          createdAt: new Date().toISOString(),
        }
      }
      return {
        id: createMessageId('assistant'),
        role: 'assistant' as const,
        kind: 'answer' as const,
        content: m.content,
        createdAt: new Date().toISOString(),
      }
    })
  }

  return {
    status,
    errorMessage,
    messages,
    sessionId,
    startRequest,
    startStreaming,
    finishResponse,
    markError,
    appendUserActionMessage,
    appendAssistantMessage,
    sendPrompt,
    reset,
    loadHistory,
  }
})
