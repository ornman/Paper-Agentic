import { beforeEach, describe, expect, it, vi, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ImportPdfButton, { validatePdfPathInput } from '../ImportPdfButton.vue'
import KnowledgeBar from '../../layout/KnowledgeBar.vue'

/**
 * 构造一个最小的 fetch Response 形状。
 */
function createFetchResponse(payload: unknown, ok = true, status = 200) {
  return {
    ok,
    status,
    async json() {
      return payload
    },
  } as const
}

describe('validatePdfPathInput (Task 6)', () => {
  it('rejects empty input', () => {
    const result = validatePdfPathInput('   ')
    expect(result.ok).toBe(false)
    expect(result.message).toContain('输入有误')
  })

  it('rejects non-local path input (URL)', () => {
    const result = validatePdfPathInput('https://evil.test/a.pdf')
    expect(result.ok).toBe(false)
    expect(result.message).toContain('输入有误')
  })

  it('rejects non-pdf extension', () => {
    const result = validatePdfPathInput('D:/papers/a.txt')
    expect(result.ok).toBe(false)
    expect(result.message).toContain('输入有误')
  })

  it('accepts a windows absolute pdf path and normalizes whitespace', () => {
    const result = validatePdfPathInput('  D:/papers/a.PDF  ')
    expect(result.ok).toBe(true)
    expect(result.normalizedPath).toBe('D:/papers/a.PDF')
  })
})

describe('ImportPdfButton pre-validation (Task 6)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.unstubAllEnvs()
  })

  it('shows "输入有误" and does not call backend when input is invalid', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(ImportPdfButton, {
      global: {
        plugins: [createPinia()],
      },
    })

    await wrapper.find('[data-testid="pdf-path-input"]').setValue('https://evil.test/a.pdf')
    await wrapper.find('[data-testid="pdf-import-submit"]').trigger('click')

    expect(fetchMock).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('输入有误')
  })

  it('calls backend only after input passes validation', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        createFetchResponse({
          code: 0,
          data: {
            document_id: 'doc-3',
            title: '',
            file_path: 'D:/papers/c.pdf',
            index_mode: 'brute',
            status: 'pending',
          },
          message: 'success',
        }),
      )
      .mockResolvedValueOnce(
        createFetchResponse({
          code: 0,
          data: [
            {
              document_id: 'doc-3',
              title: '',
              file_path: 'D:/papers/c.pdf',
              index_mode: 'brute',
              status: 'pending',
            },
          ],
          message: 'success',
        }),
      )

    vi.stubGlobal('fetch', fetchMock)
    vi.stubEnv('VITE_API_BASE_URL', 'http://127.0.0.1:8000')

    const wrapper = mount(ImportPdfButton, {
      global: {
        plugins: [createPinia()],
      },
    })

    await wrapper.find('[data-testid="pdf-path-input"]').setValue('D:/papers/c.pdf')
    await wrapper.find('[data-testid="pdf-import-submit"]').trigger('click')

    expect(fetchMock).toHaveBeenCalled()
  })

  it('keeps KnowledgeBar in unavailable semantics when initial document refresh fails', async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new Error('backend offline'))

    vi.stubGlobal('fetch', fetchMock)
    vi.stubEnv('VITE_API_BASE_URL', 'http://127.0.0.1:8000')

    const wrapper = mount(KnowledgeBar, {
      global: {
        plugins: [createPinia()],
      },
    })

    await Promise.resolve()
    await nextTick()

    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/api/v1/library/documents', undefined)
    expect(wrapper.text()).toContain('未连接')
    expect(wrapper.text()).not.toContain('导入失败')
  })
})
