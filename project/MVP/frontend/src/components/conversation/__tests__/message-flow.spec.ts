import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import AssistantMessage from '../AssistantMessage.vue'
import MessageList from '../MessageList.vue'
import UserActionMessage from '../UserActionMessage.vue'
import { useConversationStore } from '../../../stores/conversation'

describe('conversation message flow (Task 7)', () => {
  beforeEach(() => {
    // 每个用例重新创建 Pinia，避免消息列表在测试间串状态。
    setActivePinia(createPinia())
  })

  it('renders an assistant answer with source cards as part of the reply', () => {
    const wrapper = mount(AssistantMessage, {
      props: {
        message: {
          id: 'assistant-1',
          role: 'assistant',
          kind: 'answer',
          content: '建议从公共文化服务数字化角度切入。',
          createdAt: '2026-03-25T10:00:00.000Z',
          sources: [
            {
              id: 'source-1',
              title: '文献A',
              page: 12,
              snippet: '公共文化服务数字化正在重构基层文化治理路径。',
            },
          ],
        },
      },
    })

    expect(wrapper.text()).toContain('建议从公共文化服务数字化角度切入。')
    expect(wrapper.text()).toContain('参考来源')
    expect(wrapper.text()).toContain('文献A')
    expect(wrapper.text()).toContain('第 12 页')
    expect(wrapper.text()).toContain('公共文化服务数字化正在重构基层文化治理路径。')
  })

  it('renders a single-session message list with user action and assistant reply in order', () => {
    const store = useConversationStore()

    store.appendUserActionMessage({
      content: '基于当前论文草稿获取灵感',
    })

    store.appendAssistantMessage({
      content: '可以优先从研究对象、理论框架与案例比较三个层面展开。',
      sources: [
        {
          id: 'source-2',
          title: '文献B',
          page: 5,
          snippet: '研究设计需要同时交代理论框架与样本选择逻辑。',
        },
      ],
    })

    const wrapper = mount(MessageList, {
      global: {
        plugins: [createPinia()],
      },
      props: {
        messages: store.messages,
      },
    })

    const renderedMessages = wrapper.findAll('[data-testid="conversation-message"]')
    expect(renderedMessages).toHaveLength(2)
    expect(renderedMessages[0]?.attributes('data-message-role')).toBe('user')
    expect(renderedMessages[0]?.text()).toContain('触发动作')
    expect(renderedMessages[0]?.text()).toContain('基于当前论文草稿获取灵感')
    expect(renderedMessages[1]?.attributes('data-message-role')).toBe('assistant')
    expect(renderedMessages[1]?.text()).toContain('可以优先从研究对象、理论框架与案例比较三个层面展开。')
    expect(renderedMessages[1]?.text()).toContain('参考来源')
    expect(wrapper.find('[data-testid="source-card-list"]').exists()).toBe(true)
  })

  it('renders a typed prompt message with user question semantics', () => {
    const wrapper = mount(UserActionMessage, {
      props: {
        message: {
          id: 'user-prompt-1',
          role: 'user',
          kind: 'prompt',
          content: '请帮我润色这一段摘要。',
          createdAt: '2026-03-27T10:00:00.000Z',
        },
      },
    })

    expect(wrapper.text()).toContain('用户提问')
    expect(wrapper.text()).toContain('请帮我润色这一段摘要。')
  })
})
