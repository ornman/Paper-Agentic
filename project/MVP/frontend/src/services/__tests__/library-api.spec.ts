import { beforeEach, describe, expect, it, vi, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useLibraryStore } from '../../stores/library'
import { fetchLibraryDocuments } from '../api-client'

/**
 * 构造一个最小的 fetch Response 形状。
 *
 * 注意：这里不直接 new Response()，原因是 Node/JSdom 下的实现差异较多，
 * 测试只需要覆盖我们代码实际会访问的字段（ok/status/json）。
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

describe('library api integration (Task 6)', () => {
  beforeEach(() => {
    // 每个用例都重新创建 Pinia，避免 store 状态在测试之间互相污染。
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.unstubAllEnvs()
  })

  it('uses configured API base URL for library document requests', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        createFetchResponse({
          code: 0,
          data: [],
          message: 'success',
        }),
      )

    vi.stubGlobal('fetch', fetchMock)
    vi.stubEnv('VITE_API_BASE_URL', 'http://127.0.0.1:8000')

    const documents = await fetchLibraryDocuments()

    expect(documents).toEqual([])
    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/api/v1/library/documents', undefined)
  })

  it('falls back to localhost default for non-allowlisted remote API base URL', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        createFetchResponse({
          code: 0,
          data: [],
          message: 'success',
        }),
      )

    vi.stubGlobal('fetch', fetchMock)
    vi.stubEnv('VITE_API_BASE_URL', 'https://evil.example.com:9443/api')

    const documents = await fetchLibraryDocuments()

    expect(documents).toEqual([])
    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/api/v1/library/documents', undefined)
  })

  it('refreshDocuments() calls configured documents endpoint and marks empty when no documents', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        createFetchResponse({
          code: 0,
          data: [],
          message: 'success',
        }),
      )

    vi.stubGlobal('fetch', fetchMock)
    vi.stubEnv('VITE_API_BASE_URL', 'http://127.0.0.1:8000')

    const store = useLibraryStore()

    await store.refreshDocuments()

    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/api/v1/library/documents', undefined)
    expect(store.totalDocuments).toBe(0)
    expect(store.status).toBe('empty')
    expect(store.errorMessage).toBe(null)
  })

  it('refreshDocuments() keeps library unavailable and stores read failure message when backend is unreachable', async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new Error('network down'))

    vi.stubGlobal('fetch', fetchMock)
    vi.stubEnv('VITE_API_BASE_URL', 'http://127.0.0.1:8000')

    const store = useLibraryStore()

    await store.refreshDocuments()

    expect(store.status).toBe('unavailable')
    expect(store.errorMessage).toBe('知识库读取失败')
  })


  it('refreshDocuments() marks ready when backend returns at least 1 document', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        createFetchResponse({
          code: 0,
          data: [
            {
              document_id: 'doc-1',
              title: '论文A',
              file_path: 'D:/papers/a.pdf',
              index_mode: 'brute',
              status: 'pending',
            },
          ],
          message: 'success',
        }),
      )

    vi.stubGlobal('fetch', fetchMock)
    vi.stubEnv('VITE_API_BASE_URL', 'http://127.0.0.1:8000')

    const store = useLibraryStore()

    await store.refreshDocuments()

    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/api/v1/library/documents', undefined)
    expect(store.totalDocuments).toBe(1)
    expect(store.status).toBe('ready')
  })

  it('importPdf() posts file_path with index_mode=brute and transitions importing -> ready', async () => {
    const fetchMock = vi
      .fn()
      // 1) POST /import
      .mockResolvedValueOnce(
        createFetchResponse({
          code: 0,
          data: {
            document_id: 'doc-2',
            title: '',
            file_path: 'D:/papers/b.pdf',
            index_mode: 'brute',
            status: 'pending',
          },
          message: 'success',
        }),
      )
      // 2) GET /documents (导入后刷新数量)
      .mockResolvedValueOnce(
        createFetchResponse({
          code: 0,
          data: [
            {
              document_id: 'doc-2',
              title: '',
              file_path: 'D:/papers/b.pdf',
              index_mode: 'brute',
              status: 'pending',
            },
          ],
          message: 'success',
        }),
      )

    vi.stubGlobal('fetch', fetchMock)
    vi.stubEnv('VITE_API_BASE_URL', 'http://127.0.0.1:8000')

    const store = useLibraryStore()

    const promise = store.importPdf('D:/papers/b.pdf')
    expect(store.status).toBe('importing')

    await promise

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      'http://127.0.0.1:8000/api/v1/library/import',
      expect.objectContaining({
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      }),
    )

    const postBody = JSON.parse((fetchMock.mock.calls[0]?.[1] as { body?: string }).body ?? '')
    expect(postBody).toEqual({
      file_path: 'D:/papers/b.pdf',
      index_mode: 'brute',
    })

    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'http://127.0.0.1:8000/api/v1/library/documents',
      undefined,
    )

    expect(store.status).toBe('ready')
    expect(store.totalDocuments).toBe(1)
    expect(store.errorMessage).toBe(null)
  })

  it('importPdf() marks neutral import failure for backend service errors', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      createFetchResponse(
        {
          detail: 'database temporarily unavailable',
        },
        false,
        503,
      ),
    )

    vi.stubGlobal('fetch', fetchMock)
    vi.stubEnv('VITE_API_BASE_URL', 'http://127.0.0.1:8000')

    const store = useLibraryStore()

    await store.importPdf('D:/papers/unlucky.pdf')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(store.status).toBe('error')
    expect(store.errorMessage).toBe('导入失败，请稍后重试')
  })

  it('importPdf() keeps service failures neutral even when detail contains local file path text', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      createFetchResponse(
        {
          detail: '读取 D:/papers/unlucky.pdf 失败，索引服务暂时不可用',
        },
        false,
        503,
      ),
    )

    vi.stubGlobal('fetch', fetchMock)
    vi.stubEnv('VITE_API_BASE_URL', 'http://127.0.0.1:8000')

    const store = useLibraryStore()

    await store.importPdf('D:/papers/unlucky.pdf')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(store.status).toBe('error')
    expect(store.errorMessage).toBe('导入失败，请稍后重试')
  })

  it('importPdf() marks input error only when backend explicitly rejects invalid path input', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      createFetchResponse(
        {
          detail: 'file_path 字段无效：只接受 .pdf，且文件不存在',
        },
        false,
        400,
      ),
    )

    vi.stubGlobal('fetch', fetchMock)
    vi.stubEnv('VITE_API_BASE_URL', 'http://127.0.0.1:8000')

    const store = useLibraryStore()

    await store.importPdf('D:/not-exist.pdf')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(store.status).toBe('error')
    expect(store.errorMessage).toBe('输入有误')
  })
})
