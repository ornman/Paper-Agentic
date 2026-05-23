import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { HostSnapshot } from '../types/host'

export type HostStatus = 'booting' | 'ready' | 'no_document' | 'polling' | 'stale' | 'error'
export type HostSnapshotSyncKind = 'ready' | 'no_document'

export const useHostStore = defineStore('host', () => {
  // 宿主状态机仍然保留，原因是“有没有文档”与“当前处于什么生命周期阶段”不是同一件事。
  const status = ref<HostStatus>('booting')

  // 错误信息单独存放，避免 UI 只能看到 error，却不知道具体错误内容。
  const errorMessage = ref<string | null>(null)

  // Task 5 新增的宿主文档快照字段。
  // 这四个字段就是当前前端需要缓存的最小正文上下文，不向后端推送。
  const available = ref(false)
  const docTitle = ref('')
  const text = ref('')
  const updatedAt = ref<string | null>(null)

  /**
   * 进入 ready。
   * 表示宿主可用并且当前已经拥有可用文档上下文。
   */
  function markReady() {
    status.value = 'ready'
    errorMessage.value = null
  }

  /**
   * 进入 no_document。
   * 表示宿主存在，但当前没有打开可处理的 WPS 文档。
   */
  function markNoDocument() {
    status.value = 'no_document'
    errorMessage.value = null
  }

  /**
   * 进入 polling。
   * 表示轮询已经启动，但不代表一定拿到了文档。
   */
  function markPolling() {
    status.value = 'polling'
    errorMessage.value = null
  }

  /**
   * 进入 stale。
   * 表示现有宿主信息可能过期，等待后续刷新。
   */
  function markStale() {
    status.value = 'stale'
    errorMessage.value = null
  }

  /**
   * 进入 error。
   * 使用最新错误信息覆盖旧值，避免 UI 读取到过期错误。
   */
  function markError(message: string) {
    status.value = 'error'
    errorMessage.value = message
  }

  /**
   * 统一写入最新宿主快照。
   *
   * 这里显式要求调用方传入快照语义，原因是：
   * 仅凭 `available` 无法区分“当前没有文档”和“宿主临时读取失败”。
   * read_error 不应走这里，否则会重新引入把异常误判成 no_document 的旧问题。
   */
  function syncSnapshot(snapshot: HostSnapshot, kind: HostSnapshotSyncKind = snapshot.available ? 'ready' : 'no_document') {
    available.value = snapshot.available
    docTitle.value = snapshot.docTitle
    text.value = snapshot.text
    updatedAt.value = snapshot.updatedAt
    errorMessage.value = null
    status.value = kind === 'ready' ? 'ready' : 'no_document'
  }

  return {
    status,
    errorMessage,
    available,
    docTitle,
    text,
    updatedAt,
    markReady,
    markNoDocument,
    markPolling,
    markStale,
    markError,
    syncSnapshot,
  }
})
