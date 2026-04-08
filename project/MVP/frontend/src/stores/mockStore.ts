// 模拟文档类型
export interface MockDocument {
  id: string
  name: string
  path: string
  pages: number
  status: 'pending' | 'processing' | 'completed' | 'error'
  progress: number
}

// 模拟消息类型
export interface MockMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: MockSource[]
  timestamp: Date
}

// 模拟来源类型
export interface MockSource {
  id: string
  documentName: string
  page: number
  content: string
}

// 模拟会话类型
export interface MockSession {
  id: string
  title: string
  messages: MockMessage[]
  createdAt: Date
}

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useMockStore = defineStore('mock', () => {
  // 状态
  const activeTab = ref<'ingest' | 'chat' | 'settings'>('chat')
  const documents = ref<MockDocument[]>([
    { id: '1', name: '深度学习综述.pdf', path: 'D:/papers/dl-survey.pdf', pages: 45, status: 'completed', progress: 100 },
    { id: '2', name: '注意力机制详解.pdf', path: 'D:/papers/attention.pdf', pages: 23, status: 'completed', progress: 100 },
  ])

  const sessions = ref<MockSession[]>([
    {
      id: '1',
      title: '论文写作讨论',
      messages: [
        { id: '1', role: 'user', content: '什么是注意力机制？', timestamp: new Date() },
        {
          id: '2',
          role: 'assistant',
          content: '注意力机制（Attention Mechanism）是深度学习中的一种关键技术，它允许模型在处理序列数据时，动态地关注输入的不同部分。\n\n核心思想是让模型学会"关注"重要的信息，而忽略不相关的部分。在自然语言处理中，注意力机制可以帮助模型理解词语之间的关系。',
          sources: [
            { id: 's1', documentName: '注意力机制详解.pdf', page: 3, content: '注意力机制允许模型动态地关注输入的不同部分...' },
            { id: 's2', documentName: '深度学习综述.pdf', page: 12, content: 'Attention is a mechanism that allows the model to focus...' }
          ],
          timestamp: new Date()
        }
      ],
      createdAt: new Date()
    },
    {
      id: '2',
      title: '文献调研',
      messages: [],
      createdAt: new Date()
    }
  ])

  const activeSessionId = ref('1')
  const isStreaming = ref(false)
  const importProgress = ref(0)

  // 计算属性
  const activeSession = computed(() =>
    sessions.value.find(s => s.id === activeSessionId.value)
  )

  // 动作
  function setActiveTab(tab: 'ingest' | 'chat' | 'settings') {
    activeTab.value = tab
  }

  function setActiveSession(id: string) {
    activeSessionId.value = id
  }

  function addMessage(message: MockMessage) {
    const session = sessions.value.find(s => s.id === activeSessionId.value)
    if (session) {
      session.messages.push(message)
    }
  }

  function simulateImport(callback: (progress: number) => void) {
    importProgress.value = 0
    const interval = setInterval(() => {
      importProgress.value += 10
      callback(importProgress.value)
      if (importProgress.value >= 100) {
        clearInterval(interval)
      }
    }, 200)
  }

  function simulateStreamResponse(userMessage: string) {
    isStreaming.value = true

    // 添加用户消息
    addMessage({
      id: Date.now().toString(),
      role: 'user',
      content: userMessage,
      timestamp: new Date()
    })

    // 模拟 AI 响应
    const aiResponse = '这是一个模拟的 AI 响应。在实际系统中，这里会显示基于您私有文献库生成的内容，并附带来源引用。'
    const messageId = (Date.now() + 1).toString()

    // 添加空的 AI 消息
    addMessage({
      id: messageId,
      role: 'assistant',
      content: '',
      timestamp: new Date()
    })

    // 逐字显示
    let index = 0
    const interval = setInterval(() => {
      const session = sessions.value.find(s => s.id === activeSessionId.value)
      const msg = session?.messages.find(m => m.id === messageId)
      if (msg && index < aiResponse.length) {
        msg.content += aiResponse[index]
        index++
      } else {
        clearInterval(interval)
        isStreaming.value = false
        // 添加来源
        if (msg) {
          msg.sources = [
            { id: 's1', documentName: '示例文档.pdf', page: 5, content: '这是相关的引用内容...' }
          ]
        }
      }
    }, 30)
  }

  return {
    // 状态
    activeTab,
    documents,
    sessions,
    activeSessionId,
    isStreaming,
    importProgress,
    // 计算属性
    activeSession,
    // 动作
    setActiveTab,
    setActiveSession,
    addMessage,
    simulateImport,
    simulateStreamResponse
  }
})
