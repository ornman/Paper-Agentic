import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  ApiClientError,
  fetchLibraryDocuments,
  importLibraryPdf,
  type LibraryDocumentRecord,
} from '../services/api-client'

export type LibraryStatus = 'unavailable' | 'empty' | 'ready' | 'importing' | 'error'

/**
 * 复制文档列表。
 *
 * store 对外暴露的是可响应式状态；
 * 为了继续遵守不可变更新原则，这里统一返回新数组和新对象，
 * 避免把外部响应对象原地塞进 store 后又被意外修改。
 */
function cloneDocuments(documents: readonly LibraryDocumentRecord[]): LibraryDocumentRecord[] {
  return documents.map((document) => ({
    ...document,
  }))
}

export const useLibraryStore = defineStore('library', () => {
  // Task 6 开始，知识库 store 不再只是状态壳。
  // 它需要承担两个职责：
  // 1. 保存当前知识库摘要（文档数、文档列表、错误信息）
  // 2. 承接导入流程状态，让界面层只表达交互，不直接碰 HTTP 细节
  const status = ref<LibraryStatus>('unavailable')
  const errorMessage = ref<string | null>(null)
  const documents = ref<LibraryDocumentRecord[]>([])
  const totalDocuments = ref(0)

  /**
   * 根据当前文档数恢复“非错误”状态。
   */
  function restoreStatusFromDocuments() {
    if (totalDocuments.value > 0) {
      markReady()
      return
    }

    markEmpty()
  }

  /**
   * 写入最新文档列表，并同步状态。
   */
  function syncDocuments(nextDocuments: readonly LibraryDocumentRecord[]) {
    documents.value = cloneDocuments(nextDocuments)
    totalDocuments.value = documents.value.length
    restoreStatusFromDocuments()
  }

  /**
   * 标记知识库暂时为空。
   * 这和 unavailable 不同：empty 代表功能可用，只是还没有文档。
   */
  function markEmpty() {
    status.value = 'empty'
    errorMessage.value = null
  }

  /**
   * 标记知识库已可用。
   * 用于后续导入完成或已有文档可查询的场景。
   */
  function markReady() {
    status.value = 'ready'
    errorMessage.value = null
  }

  /**
   * 标记导入中。
   */
  function startImporting() {
    status.value = 'importing'
    errorMessage.value = null
  }

  /**
   * 标记知识库不可用。
   *
   * 这个状态和导入失败不是一回事：
   * unavailable 表示“当前读不到知识库后端”，
   * 因此界面不应该把它渲染成“导入失败”。
   */
  function markUnavailable(message: string | null = null) {
    status.value = 'unavailable'
    errorMessage.value = message
  }

  /**
   * 标记错误状态并记录最新错误。
   */
  function markError(message: string) {
    status.value = 'error'
    errorMessage.value = message
  }

  /**
   * 清除错误，并根据当前文档数恢复到 empty / ready。
   *
   * 这个动作主要给输入组件使用：
   * 用户开始修改路径时，旧的错误提示不应该一直挂在界面上。
   */
  function clearError() {
    if (!errorMessage.value) {
      return
    }

    // 如果当前错误来自“知识库读取失败”，
    // 用户修改导入路径并不能证明后端已经恢复；
    // 因此这里只清掉提示文本，但保留 unavailable 语义。
    if (status.value === 'unavailable') {
      markUnavailable()
      return
    }

    restoreStatusFromDocuments()
  }

  /**
   * 从后端刷新知识库文档列表。
   */
  async function refreshDocuments() {
    try {
      const nextDocuments = await fetchLibraryDocuments()
      syncDocuments(nextDocuments)
    } catch {
      // 读取失败不等于“导入失败”：
      // - 可能是后端未启动
      // - 可能是网络/跨域问题
      // - 也可能是 API base URL 配置错误
      // 此时更合理的语义是“知识库不可用”。
      markUnavailable('知识库读取失败')
    }
  }

  /**
   * 判断导入失败是否属于“路径输入错误”。
   *
   * 设计原则：
   * 1. 必须先看 HTTP 状态码，只有输入边界类错误才有资格继续判定；
   * 2. 再看“明确路径非法”的关键词，而不是泛化词；
   * 3. 这样可以避免 5xx 服务故障因为 message 里带了本地路径，就被误判成“输入有误”。
   */
  function isInvalidPathError(error: unknown): boolean {
    if (!(error instanceof ApiClientError)) {
      return false
    }

    const isInputBoundaryStatus = error.statusCode === 400 || error.statusCode === 422

    if (!isInputBoundaryStatus) {
      return false
    }

    const normalizedMessage = error.message.toLowerCase()
    const explicitInvalidPathKeywords = [
      'file_path',
      '本地 pdf 文件路径',
      '只接受 .pdf',
      '文件不存在',
    ]

    return explicitInvalidPathKeywords.some((keyword) => normalizedMessage.includes(keyword))
  }

  /**
   * 把导入成功但列表刷新失败的文档先合并进本地状态。
   *
   * 原因是：
   * 后端已经接受导入请求时，前端不能因为随后的列表刷新失败，
   * 就把这次导入误报成完全失败。
   */
  function mergeImportedDocument(importedDocument: LibraryDocumentRecord) {
    const existingDocument = documents.value.find(
      (document) => document.document_id === importedDocument.document_id,
    )

    const nextDocuments = existingDocument
      ? documents.value.map((document) => {
          if (document.document_id !== importedDocument.document_id) {
            return {
              ...document,
            }
          }

          return {
            ...importedDocument,
          }
        })
      : [...cloneDocuments(documents.value), { ...importedDocument }]

    syncDocuments(nextDocuments)
  }

  /**
   * 提交 PDF 导入请求。
   *
   * 语义约束：
   * 1. 进入请求前先同步到 importing；
   * 2. 只有“前端路径校验失败”或“后端明确指出路径非法”时，才回写“输入有误”；
   * 3. 其他导入失败统一用中性失败文案，避免把服务故障伪装成用户输入问题；
   * 4. 导入成功后再刷新文档列表；
   * 5. 不提前接 Task 8 的 SSE 进度流。
   */
  async function importPdf(filePath: string) {
    startImporting()

    try {
      const importedDocument = await importLibraryPdf(filePath)

      try {
        const nextDocuments = await fetchLibraryDocuments()
        syncDocuments(nextDocuments)
      } catch {
        mergeImportedDocument(importedDocument)
      }
    } catch (error) {
      if (isInvalidPathError(error)) {
        markError('输入有误')
        return
      }

      markError('导入失败，请稍后重试')
    }
  }

  return {
    status,
    errorMessage,
    documents,
    totalDocuments,
    markEmpty,
    markReady,
    startImporting,
    markUnavailable,
    markError,
    clearError,
    syncDocuments,
    refreshDocuments,
    importPdf,
  }
})
