import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { SourceCard } from '../components/conversation/SourceCardList.vue'
import { ApiClientError } from '../services/api-client'
import { postAskInspirationStream } from '../services/sse-client'
import type { AskInspirationRequestPayload } from '../services/sse-client'

export type ConversationStatus = 'idle' | 'requesting' | 'streaming' | 'done' | 'error'

/**
 * 用户动作消息：强调“用户触发了一个论文创作动作”，而不是普通聊天输入。
 */
export interface ConversationUserActionMessage {
  id: string
  role: 'user'
  kind: 'action' | 'prompt'
  content: string
  createdAt: string
}

/**
 * 助手回复消息：可携带来源列表。
 *
 * 注意：来源区是回复的一部分，因此 sources 直接挂在消息上，
 * 后续由 AssistantMessage 内部渲染，而不是在外层单独挂一个附件区域。
 */
export interface ConversationAssistantMessage {
  id: string
  role: 'assistant'
  kind: 'answer'
  content: string
  createdAt: string
  sources?: SourceCard[]
}

export type ConversationRecord = ConversationUserActionMessage | ConversationAssistantMessage

/**
 * 生成稳定但足够轻量的前端临时消息 ID。
 *
 * 原因：
 * - Task 7 只需要本地渲染 key，不需要和后端 ID 对齐；
 * - 不能提前引入 SSE / 历史会话的真实 ID 规则；
 * - 用时间戳 + 递增序号即可满足当前单会话场景。
 */
let messageSequence = 0

function createMessageId(prefix: 'user' | 'assistant') {
  messageSequence += 1
  return `${prefix}-${Date.now()}-${messageSequence}`
}

/**
 * 生成当前前端单会话使用的 session_id。
 *
 * 设计目标：
 * - 不能再写死成固定字面量，否则后端会把不同文档/不同打开周期混到同一历史里；
 * - 在当前前端单会话生命周期内必须稳定复用；
 * - reset 后重新生成，显式切断上一轮上下文。
 */
function createSessionId() {
  const uuid = globalThis.crypto?.randomUUID?.()

  if (uuid) {
    return `frontend-session-${uuid}`
  }

  return `frontend-session-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

/**
 * 复制来源卡片数组。
 *
 * 保持 store 对外暴露不可变数据，
 * 避免组件层拿到引用后原地修改，反向污染状态中心。
 */
function cloneSources(sources: readonly SourceCard[] | undefined): SourceCard[] | undefined {
  if (!sources) {
    return undefined
  }

  return sources.map((source) => ({
    ...source,
  }))
}

export const useConversationStore = defineStore('conversation', () => {
  // Task 7 在保留状态机的基础上，补上“当前单会话消息列表”。
  // 仍然只维护前端内存态：
  // - 不接历史数据
  // - 不接 SSE
  // - 不做多会话
  const status = ref<ConversationStatus>('idle')
  const errorMessage = ref<string | null>(null)
  const messages = ref<ConversationRecord[]>([])

  // 🔴 P1-2 优化：重试状态管理
  const retryState = ref({
    canRetry: false,
    lastPayload: null as AskInspirationRequestPayload | null,
    retryCount: 0
  })

  /**
   * 当前前端单会话的 session_id。
   *
   * 说明：
   * - 该值只服务于“前端一次打开周期内”的连续请求；
   * - reset() 必须生成新值，从而让后端历史隔离。
   */
  const sessionId = ref<string>(createSessionId())
  const promptContext = ref('')
  const selectionContext = ref('')

  /**
   * 当前流式回复对应的助手消息 ID。
   *
   * 为什么单独记这个值？
   * 因为 chunk / sources / done 会在一次请求生命周期内多次到达，
   * store 需要知道“正在被增量更新的是哪一条助手消息”。
   */
  const activeAssistantMessageId = ref<string | null>(null)

  /**
   * 暂存“已经收到，但还没资格挂到 assistant message 上”的来源。
   *
   * 为什么要暂存？
   * - 来源区本质上属于回复正文的一部分；
   * - 如果 sources 比第一个 chunk 更早到达，直接建 assistant message 会制造空壳回复；
   * - 一旦随后直接 error，就会留下“只有来源没有正文”的脏消息。
   *
   * 因此这里改成：
   * 1. sources 先暂存；
   * 2. 首个 chunk 到来时再真正创建 assistant message，并把暂存来源一起挂上；
   * 3. 若 chunk 前直接 error/reset，则直接丢弃暂存来源。
   */
  const pendingAssistantSources = ref<SourceCard[] | null>(null)

  /**
   * 进入 requesting。
   * 表示用户已发起请求，但还没有开始收到流式响应。
   */
  function startRequest() {
    status.value = 'requesting'
    errorMessage.value = null

    // 新一轮请求开始时，必须清理上一轮残留的流式上下文。
    // 否则会出现：
    // - 新 chunk 追加到旧 assistant message 上
    // - 旧 sources 被错误挂载到新回复上
    activeAssistantMessageId.value = null
    pendingAssistantSources.value = null
  }

  /**
   * 进入 streaming。
   * 真正的 SSE 接入放到后续任务，这里只保留状态转移动作。
   */
  function startStreaming() {
    status.value = 'streaming'
    errorMessage.value = null
  }

  /**
   * 进入 done。
   * 表示一次响应生命周期正常结束。
   */
  function finishResponse() {
    status.value = 'done'
    errorMessage.value = null
  }

  /**
   * 进入 error 并记录错误消息。
   */
  function markError(message: string) {
    status.value = 'error'
    errorMessage.value = message
  }

  /**
   * 追加“用户动作消息”。
   *
   * 为什么不是 sendUserMessage？
   * 因为当前产品语义不是聊天输入，而是动作触发。
   */
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

  /**
   * 追加助手回复消息。
   *
   * Task 8 虽然已经开始支持流式更新，
   * 但这里仍然保留“直接追加完整回复”的能力，避免打坏 Task 7 的既有测试。
   */
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

  /**
   * 为当前请求创建一个“待流式填充”的助手消息壳。
   *
   * 这样消息区可以在第一个 chunk 到来之前就稳定占位，
   * 避免后续来源卡片或文本更新时找不到目标消息。
   */
  function createStreamingAssistantMessage(createdAt?: string): string {
    const nextMessage: ConversationAssistantMessage = {
      id: createMessageId('assistant'),
      role: 'assistant',
      kind: 'answer',
      content: '',
      createdAt: createdAt ?? new Date().toISOString(),
      // 只有在正文真正开始出现时，才把此前暂存的来源挂上去。
      sources: cloneSources(pendingAssistantSources.value ?? undefined),
    }

    activeAssistantMessageId.value = nextMessage.id
    pendingAssistantSources.value = null
    messages.value = [...messages.value, nextMessage]
    return nextMessage.id
  }

  /**
   * 更新当前流式中的助手消息。
   *
   * 采用不可变更新，而不是原地修改数组元素，
   * 继续遵守当前项目的状态管理约束。
   */
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

  /**
   * 追加一个 chunk 到当前助手回复正文末尾。
   */
  function ensureStreamingAssistantMessage(): string {
    if (activeAssistantMessageId.value) {
      return activeAssistantMessageId.value
    }

    return createStreamingAssistantMessage()
  }

  /**
   * 追加一个 chunk 到当前助手回复正文末尾。
   */
  function appendAssistantChunk(chunkText: string) {
    if (!chunkText) {
      return
    }

    const messageId = ensureStreamingAssistantMessage()

    updateAssistantMessage(messageId, (message) => ({
      ...message,
      content: `${message.content}${chunkText}`,
    }))
  }

  /**
   * 把来源列表挂到当前助手回复上。
   */
  function attachAssistantSources(sources: SourceCard[]) {
    if (sources.length === 0) {
      return
    }

    // 只有正文已经开始流出时，assistant message 才真正存在。
    // 否则先暂存，等待首个 chunk 到来后再一起挂载。
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

  /**
   * 执行 Task 8 的“获取灵感”动作。
   *
   * 当前严格锁死场景 1：
   * - 不接圈选文本
   * - 不接用户补充 prompt
   * - 不接真实历史会话
   */
  function setPromptContext(value: string) {
    promptContext.value = value.trim()
  }

  function setSelectionContext(value: string) {
    selectionContext.value = value.trim()
  }

  async function askInspiration(payload: AskInspirationRequestPayload) {
    startRequest()
    appendUserActionMessage({
      content: '基于当前论文草稿获取灵感',
      kind: 'action',
    })

    // 🔴 P1-2 优化：保存 payload 用于重试
    retryState.value.lastPayload = payload
    retryState.value.canRetry = false

    // 注意：不要在拿到任何 chunk 之前就创建空的 assistant message。
    //
    // 原因：
    // - 一旦 SSE 直接返回 error 事件，UI 会留下“空白助手气泡”，用户不知道发生了什么；
    // - 正确的行为是：只有确认收到内容/来源后，才创建并增量填充 assistant message。

    try {
      // 🔴 P1-2 优化：使用带重试的 SSE 请求
      const { postAskInspirationStreamWithRetry } = await import('../services/sse-client')

      await postAskInspirationStreamWithRetry(payload, {
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
          // 🔴 P1-2 优化：成功后清除重试状态
          retryState.value.canRetry = false
          retryState.value.retryCount = 0
        },
        onErrorEvent(message) {
          markError(message)
          activeAssistantMessageId.value = null
          pendingAssistantSources.value = null
          // 🔴 P1-2 优化：错误时允许重试
          retryState.value.canRetry = true
        },
      })

      // 某些后端实现可能直接结束流，而没有显式发出 done 事件。
      // 当前保持最小兜底：只要没有进入 error，结束时就视为完成。
      if (status.value !== 'error') {
        finishResponse()
        activeAssistantMessageId.value = null
        pendingAssistantSources.value = null
      }
    } catch (error) {
      const message =
        error instanceof ApiClientError || error instanceof Error
          ? error.message
          : '获取灵感失败，请稍后重试'

      markError(message)
      activeAssistantMessageId.value = null
      pendingAssistantSources.value = null
      // 🔴 P1-2 优化：错误时允许重试并增加重试计数
      retryState.value.canRetry = true
      retryState.value.retryCount++
    }
  }

  async function sendPrompt(payload: AskInspirationRequestPayload) {
    startRequest()
    appendUserActionMessage({
      content: payload.query,
      kind: 'prompt',
    })

    try {
      await postAskInspirationStream(payload, {
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
          // 🔴 P1-2 优化：成功后清除重试状态
          retryState.value.canRetry = false
          retryState.value.retryCount = 0
        },
        onErrorEvent(message) {
          markError(message)
          activeAssistantMessageId.value = null
          pendingAssistantSources.value = null
          // 🔴 P1-2 优化：错误时允许重试
          retryState.value.canRetry = true
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

  /**
   * 重置到 idle，并清空当前单会话消息。
   * 作用是给下一轮请求一个干净起点。
   */
  function reset() {
    status.value = 'idle'
    errorMessage.value = null
    messages.value = []
    activeAssistantMessageId.value = null
    pendingAssistantSources.value = null
    promptContext.value = ''
    selectionContext.value = ''

    // reset 的语义是“开始新会话”，因此 session_id 必须刷新。
    sessionId.value = createSessionId()
  }

  return {
    status,
    errorMessage,
    messages,
    // 让 UI 层只读当前 session_id，用于构造后端请求。
    // 注意：reset() 会刷新它，达到“新会话新 id”的隔离效果。
    sessionId,
    promptContext,
    selectionContext,
    startRequest,
    startStreaming,
    finishResponse,
    markError,
    appendUserActionMessage,
    appendAssistantMessage,
    setPromptContext,
    setSelectionContext,
    askInspiration,
    sendPrompt,
    reset,
  }
})
