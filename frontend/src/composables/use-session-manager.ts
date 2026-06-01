import { ref } from 'vue'
import type { ConversationSession } from '../types/conversation'
import type { ConversationRecord, UserMessage, AssistantMessage } from '../types/message'
import type { ContentBlock } from '../types/content'
import { listSessions, deleteSession, getMessages } from '../services/conversation-api'
import type { useConversationStore } from '../stores/conversation'
import type { useLibraryStore } from '../stores/library'
import type { useUiStore } from '../stores/ui'

export interface SessionManagerOptions {
  store: ReturnType<typeof useConversationStore>
  libraryStore: ReturnType<typeof useLibraryStore>
  uiStore: ReturnType<typeof useUiStore>
  demoActive: { value: boolean }
}

/**
 * 会话列表 CRUD + 切换 + demo 模式数据加载。
 */
export function useSessionManager(opts: SessionManagerOptions) {
  const sessions = ref<ConversationSession[]>([])
  const sessionsLoading = ref(false)

  async function handleOpenHistory() {
    opts.uiStore.openSidebar('history')
    if (opts.demoActive.value) return
    sessionsLoading.value = true
    try {
      sessions.value = await listSessions()
    } catch {
      sessions.value = []
    } finally {
      sessionsLoading.value = false
    }
  }

  async function switchToSession(sessionId: string) {
    const { DEMO_SESSIONS } = await import('../demo')

    // Demo 模式：从 mock 数据加载
    if (opts.demoActive.value) {
      const demoSession = DEMO_SESSIONS.find(s => s.session_id === sessionId)
      opts.store.reset()
      opts.store.sessionId = sessionId
      if (demoSession) {
        opts.store.messages = [...demoSession.messages]
      }
      opts.uiStore.closeSidebar()
      return
    }

    try {
      const msgs = await getMessages(sessionId)
      opts.store.reset()
      opts.store.sessionId = sessionId
      const mapped: ConversationRecord[] = []
      for (const msg of msgs) {
        if (msg.role === 'user') {
          mapped.push({
            id: `user-${msg.created_at}`,
            role: 'user',
            content: msg.content,
            createdAt: msg.created_at,
          } as UserMessage)
        } else if (msg.role === 'assistant') {
          let blocks: AssistantMessage['blocks']
          if (msg.blocks_json) {
            try {
              const parsed = JSON.parse(msg.blocks_json)
              if (Array.isArray(parsed) && parsed.length > 0) {
                blocks = parsed.filter(
                  (b): b is ContentBlock =>
                    typeof b === 'object' && b !== null && typeof b.type === 'string'
                )
                if (blocks.length === 0) {
                  blocks = [{ type: 'paragraph' as const, text: msg.content }]
                }
              } else {
                blocks = [{ type: 'paragraph' as const, text: msg.content }]
              }
            } catch {
              blocks = [{ type: 'paragraph' as const, text: msg.content }]
            }
          } else {
            blocks = [{ type: 'paragraph' as const, text: msg.content }]
          }

          let sources: AssistantMessage['sources']
          if (msg.sources_json) {
            try {
              const parsed = JSON.parse(msg.sources_json)
              sources = Array.isArray(parsed) ? parsed : []
            } catch {
              sources = []
            }
          } else {
            sources = []
          }

          mapped.push({
            id: `assistant-${msg.created_at}`,
            role: 'assistant',
            createdAt: msg.created_at,
            thinking: '',
            thinkingTimeMs: 0,
            blocks,
            sources,
          } as AssistantMessage)
        }
      }
      opts.store.messages = mapped
    } catch {
      opts.store.reset()
      opts.store.sessionId = sessionId
    }
    opts.uiStore.closeSidebar()
    opts.libraryStore.clearSelectedPapers()
  }

  async function handleDeleteSession(sessionId: string) {
    if (opts.demoActive.value) {
      sessions.value = sessions.value.filter((s) => s.session_id !== sessionId)
      if (opts.store.sessionId === sessionId) {
        opts.store.reset()
        opts.libraryStore.clearSelectedPapers()
      }
      return
    }
    try {
      await deleteSession(sessionId)
      sessions.value = sessions.value.filter((s) => s.session_id !== sessionId)
      if (opts.store.sessionId === sessionId) {
        opts.store.reset()
        opts.libraryStore.clearSelectedPapers()
      }
    } catch {
      // 静默失败，保留列表原样
    }
  }

  return {
    sessions,
    sessionsLoading,
    handleOpenHistory,
    switchToSession,
    handleDeleteSession,
  }
}
