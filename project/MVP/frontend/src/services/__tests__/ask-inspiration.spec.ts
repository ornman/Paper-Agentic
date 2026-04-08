import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import AppShell from '../../app/AppShell.vue'
import { useConversationStore } from '../../stores/conversation'

interface SseEventFixture {
  event: 'chunk' | 'sources' | 'done' | 'error'
  data: unknown
}

function createJsonResponse(payload: unknown, ok = true, status = 200) {
  return {
    ok,
    status,
    async json() {
      return payload
    },
  } as const
}

function serializeSseEvent(event: SseEventFixture): string {
  return `event: ${event.event}\ndata: ${JSON.stringify(event.data)}\n\n`
}

function createSseResponse(events: SseEventFixture[]) {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const event of events) {
        const frame = serializeSseEvent(event)
        const middleIndex = Math.max(1, Math.floor(frame.length / 2))
        controller.enqueue(encoder.encode(frame.slice(0, middleIndex)))
        controller.enqueue(encoder.encode(frame.slice(middleIndex)))
      }

      controller.close()
    },
  })

  return {
    ok: true,
    status: 200,
    body,
  } as const
}

function createWpsApiWithDocument(text: string, available = true, selectionText = '') {
  return {
    WpsApplication() {
      return {
        ActiveDocument: available
          ? {
              Name: '论文草稿.docx',
              Content: {
                Text: text,
              },
            }
          : null,
        ActiveWindow: {
          Selection: {
            Text: selectionText,
          },
        },
      }
    },
  }
}

describe('chat composer flow', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.unstubAllEnvs()
  })

  it('clicking 发送 posts backend-compatible payload and renders user prompt, streamed answer, and mapped sources', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      void init
      const url = String(input)

      if (url.endsWith('/api/v1/library/documents')) {
        return createJsonResponse({
          code: 0,
          data: [],
          message: 'success',
        })
      }

      if (url.endsWith('/api/v1/query/ask')) {
        return createSseResponse([
          {
            event: 'sources',
            data: {
              sources: [
                {
                  id: 1,
                  document: '文献A',
                  page: 7,
                  content: '理论框架与案例比较能够提升论文论证的完整度。',
                },
              ],
            },
          },
          {
            event: 'chunk',
            data: {
              content: '可以先从研究问题切入。',
            },
          },
          {
            event: 'chunk',
            data: {
              content: '再补充理论框架与案例比较。',
            },
          },
          {
            event: 'done',
            data: {
              total_tokens: 42,
            },
          },
        ])
      }

      throw new Error(`Unexpected fetch: ${url}`)
    })

    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('wps', createWpsApiWithDocument('当前论文正文内容', true, '用户刚刚圈选的段落'))

    const pinia = createPinia()
    setActivePinia(pinia)

    const wrapper = mount(AppShell, {
      global: {
        plugins: [pinia],
      },
    })

    await flushPromises()

    const composer = wrapper.find('[data-testid="bottom-action-bar"] .composer-input')
    await composer.setValue('请基于当前论文草稿给我一个摘要框架')

    const actionButton = wrapper.find('[data-testid="bottom-action-bar"] .primary-button')
    expect(actionButton.exists()).toBe(true)
    expect(actionButton.attributes('aria-label')).toBe('发送消息')
    expect(actionButton.attributes('disabled')).toBeUndefined()

    await actionButton.trigger('click')
    await flushPromises()
    await flushPromises()

    const askCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/api/v1/query/ask'))
    expect(askCall).toBeTruthy()

    const requestInit = askCall?.[1] as RequestInit | undefined
    expect(requestInit).toMatchObject({
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
    })
    const askPayload = JSON.parse(String(requestInit?.body ?? '')) as Record<string, unknown>

    expect(askPayload.session_id).toEqual(expect.any(String))
    expect(String(askPayload.session_id)).not.toBe('')
    expect(askPayload).toMatchObject({
      query: '请基于当前论文草稿给我一个摘要框架',
      context: {
        written_content: '当前论文正文内容',
        selected_text: '用户刚刚圈选的段落',
        prompt: '请基于当前论文草稿给我一个摘要框架',
      },
    })

    expect(wrapper.find('[data-testid="message-list"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('用户提问')
    expect(wrapper.text()).toContain('请基于当前论文草稿给我一个摘要框架')
    expect(wrapper.text()).toContain('可以先从研究问题切入。再补充理论框架与案例比较。')
    expect(wrapper.text()).toContain('参考来源')
    expect(wrapper.text()).toContain('文献A')
    expect(wrapper.text()).toContain('第 7 页')
    expect(wrapper.text()).toContain('理论框架与案例比较能够提升论文论证的完整度。')

    const conversationStore = useConversationStore()
    expect(conversationStore.status).toBe('done')
    expect(conversationStore.errorMessage).toBe(null)
    expect(conversationStore.messages).toHaveLength(2)
  })

  it('does not keep an assistant message when SSE sends sources before error, and shows a visible error message', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)

      if (url.endsWith('/api/v1/library/documents')) {
        return createJsonResponse({
          code: 0,
          data: [],
          message: 'success',
        })
      }

      if (url.endsWith('/api/v1/query/ask')) {
        return createSseResponse([
          {
            event: 'sources',
            data: {
              sources: [
                {
                  id: 9,
                  document: '文献B',
                  page: 3,
                  content: '这一条来源不应该在错误路径里单独残留成助手回复。',
                },
              ],
            },
          },
          {
            event: 'error',
            data: {
              message: '检索失败，请稍后重试',
            },
          },
        ])
      }

      throw new Error(`Unexpected fetch: ${url}`)
    })

    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('wps', createWpsApiWithDocument('另一段论文正文'))

    const pinia = createPinia()
    setActivePinia(pinia)

    const wrapper = mount(AppShell, {
      global: {
        plugins: [pinia],
      },
    })

    await flushPromises()
    await wrapper.find('[data-testid="bottom-action-bar"] .composer-input').setValue('请帮我梳理这段正文的问题')
    await wrapper.find('[data-testid="bottom-action-bar"] .primary-button').trigger('click')
    await flushPromises()
    await flushPromises()

    const conversationStore = useConversationStore()
    expect(conversationStore.status).toBe('error')
    expect(conversationStore.errorMessage).toBe('检索失败，请稍后重试')
    expect(conversationStore.messages).toHaveLength(1)
    expect(conversationStore.messages[0]?.role).toBe('user')

    expect(wrapper.text()).toContain('请帮我梳理这段正文的问题')
    expect(wrapper.text()).toContain('检索失败，请稍后重试')
    expect(wrapper.findAll('[data-testid="assistant-message"]')).toHaveLength(0)
    expect(wrapper.text()).not.toContain('文献B')
    expect(wrapper.text()).not.toContain('这一条来源不应该在错误路径里单独残留成助手回复。')
  })

  it('disables send button and does not send request when prompt is empty and host is unavailable', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)

      if (url.endsWith('/api/v1/library/documents')) {
        return createJsonResponse({
          code: 0,
          data: [],
          message: 'success',
        })
      }

      throw new Error(`Unexpected fetch: ${url}`)
    })

    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('wps', createWpsApiWithDocument('', false))

    const pinia = createPinia()
    setActivePinia(pinia)

    const wrapper = mount(AppShell, {
      global: {
        plugins: [pinia],
      },
    })

    await flushPromises()

    const actionButton = wrapper.find('[data-testid="bottom-action-bar"] .primary-button')
    expect(actionButton.attributes('aria-label')).toBe('发送消息')
    expect(actionButton.attributes('disabled')).toBeDefined()

    await actionButton.trigger('click')
    await flushPromises()

    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/api/v1/query/ask'))).toBe(false)
  })

  it('disables send button and does not send request when prompt is empty even if document text exists', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)

      if (url.endsWith('/api/v1/library/documents')) {
        return createJsonResponse({
          code: 0,
          data: [],
          message: 'success',
        })
      }

      throw new Error(`Unexpected fetch: ${url}`)
    })

    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('wps', createWpsApiWithDocument('   '))

    const pinia = createPinia()
    setActivePinia(pinia)

    const wrapper = mount(AppShell, {
      global: {
        plugins: [pinia],
      },
    })

    await flushPromises()

    const actionButton = wrapper.find('[data-testid="bottom-action-bar"] .primary-button')
    expect(actionButton.attributes('disabled')).toBeDefined()

    await actionButton.trigger('click')
    await flushPromises()

    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/api/v1/query/ask'))).toBe(false)
  })

  it('sends a typed prompt to the real ask endpoint even when host document is unavailable', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      void init

      if (url.endsWith('/api/v1/library/documents')) {
        return createJsonResponse({
          code: 0,
          data: [],
          message: 'success',
        })
      }

      if (url.endsWith('/api/v1/query/ask')) {
        return createSseResponse([
          {
            event: 'chunk',
            data: {
              content: '这是来自真实问答链路的前端流式渲染测试回复。',
            },
          },
          {
            event: 'done',
            data: {
              total_tokens: 21,
            },
          },
        ])
      }

      throw new Error(`Unexpected fetch: ${url}`)
    })

    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('wps', createWpsApiWithDocument('', false))

    const pinia = createPinia()
    setActivePinia(pinia)

    const wrapper = mount(AppShell, {
      global: {
        plugins: [pinia],
      },
    })

    await flushPromises()

    const composer = wrapper.find('[data-testid="bottom-action-bar"] .composer-input')
    await composer.setValue('请直接帮我概括这个研究问题的写作方向')

    const actionButton = wrapper.find('[data-testid="bottom-action-bar"] .primary-button')
    expect(actionButton.attributes('aria-label')).toBe('发送消息')
    expect(actionButton.attributes('disabled')).toBeUndefined()

    await actionButton.trigger('click')
    await flushPromises()
    await flushPromises()

    const askCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/api/v1/query/ask'))
    expect(askCall).toBeTruthy()

    const [, requestInit] = askCall as [RequestInfo | URL, RequestInit | undefined]
    const askPayload = JSON.parse(String(requestInit?.body ?? '')) as Record<string, unknown>

    expect(askPayload.query).toBe('请直接帮我概括这个研究问题的写作方向')
    expect(wrapper.text()).toContain('请直接帮我概括这个研究问题的写作方向')
    expect(wrapper.text()).toContain('这是来自真实问答链路的前端流式渲染测试回复。')
  })
})
