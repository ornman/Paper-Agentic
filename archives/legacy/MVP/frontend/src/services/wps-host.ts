import type { HostSnapshot } from '../types/host'
import type { HostSnapshotSyncKind } from '../stores/host'

/**
 * Task 5 约定的固定轮询周期。
 *
 * 这里直接导出常量，而不是把数值散落到组件和测试里，
 * 原因是“5 秒”是当前版本的业务约束，不是随手写的魔法数字。
 */
export const WPS_POLLING_INTERVAL_MS = 5000

/**
 * WPS 文档对象的最小可读形状。
 *
 * 当前任务只关心文档标题和全文文本，
 * 不提前接选区、批注、段落结构等后续能力。
 */
export interface WpsDocumentLike {
  Name?: unknown
  Content?: {
    Text?: unknown
  } | null
}

/**
 * WPS 应用实例的最小形状。
 *
 * ActiveDocument 是否存在，直接决定当前前端是否拥有可用文档上下文。
 */
export interface WpsApplicationLike {
  ActiveDocument?: WpsDocumentLike | null
}

/**
 * WPS JS API 的最小形状。
 *
 * 第一版只读取 `WpsApplication()`，
 * 不把 Task 6 的后端 API、Task 8 的 SSE 能力提前耦合进来。
 */
export interface WpsApiLike {
  WpsApplication?: () => WpsApplicationLike | null | undefined
}

/**
 * 宿主 store 的最小可写契约。
 *
 * 这里不直接依赖具体 Pinia store 类型，而是只声明 Task 5 真正需要的写入面，
 * 这样宿主服务层仍然保持“只认识数据契约，不认识具体 UI 实现”。
 */
export interface HostStoreWritable {
  available: boolean
  docTitle: string
  text: string
  updatedAt: string | null
  markReady?: () => void
  markNoDocument?: () => void
  markPolling?: () => void
  markStale?: () => void
  markError?: (message: string) => void
  syncSnapshot?: (snapshot: HostSnapshot, kind?: HostSnapshotSyncKind) => void
}

/**
 * 前端使用的宿主适配器最小契约。
 *
 * Task 4 提供了一次性读取；
 * Task 5 在此基础上补上：
 * - `pollOnce`：单次读取并可写入 store
 * - `startPolling`：启动固定 5 秒轮询
 * - `stopPolling`：组件卸载时清理定时器
 */
export interface WpsHostAdapter {
  startPolling: (hostStore?: HostStoreWritable) => Promise<void>
  stopPolling: () => void
  pollOnce: (hostStore?: HostStoreWritable) => Promise<HostSnapshot>
  getSnapshot: () => HostSnapshot
}

/**
 * 轮询读取结果。
 *
 * 这里把“没有文档”和“读取出错”显式拆开，
 * 因为它们的语义完全不同：
 * - no_document：宿主成功响应，但当前确实没有活动文档
 * - read_error：宿主暂时异常，不能据此抹掉上一份成功快照
 */
interface HostReadResult {
  kind: 'ready' | 'no_document' | 'read_error'
  snapshot: HostSnapshot
}

/**
 * 生成带类型的读取结果。
 */
function createReadResult(kind: HostReadResult['kind'], snapshot: HostSnapshot): HostReadResult {
  return {
    kind,
    snapshot,
  }
}

/**
 * 生成不可用快照。
 *
 * 每次都返回新对象，而不是复用共享引用，
 * 这样可以避免可变对象在不同调用方之间互相污染。
 */
function createUnavailableSnapshot(): HostSnapshot {
  return {
    available: false,
    docTitle: '',
    text: '',
    updatedAt: null,
  }
}

/**
 * 复制快照。
 *
 * 服务层内部保留自己的快照引用，对外一律返回副本，
 * 这样可以继续遵守不可变暴露原则。
 */
function cloneSnapshot(snapshot: HostSnapshot): HostSnapshot {
  return {
    ...snapshot,
  }
}

/**
 * 把不可信输入收敛成字符串。
 *
 * WPS 宿主对象来自外部运行时，不能假设它一定严格符合声明类型。
 */
function normalizeString(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

/**
 * 生成读取异常时的占位快照。
 *
 * 这个快照不会直接覆盖 store 中上一份成功结果，
 * 它只用于适配器内部表达“这次读取失败了”。
 */
function createReadErrorSnapshot(): HostSnapshot {
  return {
    available: false,
    docTitle: '',
    text: '',
    updatedAt: null,
  }
}

/**
 * 从 WPS Application 快照中提取前端真正关心的最小状态。
 */
function createSnapshotFromApplication(
  application: WpsApplicationLike | null | undefined,
): HostSnapshot {
  const activeDocument = application?.ActiveDocument

  if (!activeDocument) {
    return createUnavailableSnapshot()
  }

  return {
    available: true,
    docTitle: normalizeString(activeDocument.Name),
    text: normalizeString(activeDocument.Content?.Text),
    updatedAt: new Date().toISOString(),
  }
}

/**
 * 解析当前可用的 WPS API。
 *
 * 优先使用显式传入的 fake API，便于测试；
 * 如果调用方没有传，则再尝试从全局运行时读取真实 `wps` 对象。
 */
function resolveWpsApi(explicitApi?: WpsApiLike): WpsApiLike | undefined {
  if (explicitApi) {
    return explicitApi
  }

  const runtime = globalThis as typeof globalThis & { wps?: WpsApiLike }
  return runtime.wps
}

/**
 * 从宿主读取一次最新结果。
 *
 * 关键变化：
 * 1. `no_document` 表示宿主读成功，但当前确实没有活动文档
 * 2. `read_error` 表示宿主临时异常，不能被误判成“当前没有文档”
 */
function readSnapshotFromApi(wpsApi?: WpsApiLike): HostReadResult {
  if (!wpsApi?.WpsApplication) {
    return createReadResult('no_document', createUnavailableSnapshot())
  }

  try {
    const application = wpsApi.WpsApplication()
    const snapshot = createSnapshotFromApplication(application)

    return createReadResult(snapshot.available ? 'ready' : 'no_document', snapshot)
  } catch {
    return createReadResult('read_error', createReadErrorSnapshot())
  }
}

/**
 * 把宿主读取结果写入 host store。
 *
 * 设计重点：
 * 1. ready / no_document / read_error 三类结果必须显式区分
 * 2. read_error 时保留上一份成功快照，避免 UI 抖动时误清空当前上下文
 * 3. 如果 store 暴露了 `syncSnapshot`，只在可安全覆盖快照时调用它
 */
function writeReadResultToHostStore(
  hostStore: HostStoreWritable | undefined,
  readResult: HostReadResult,
): void {
  if (!hostStore) {
    return
  }

  if (readResult.kind === 'read_error') {
    // 短暂读取异常只说明“这次刷新失败了”，不说明宿主已经进入不可恢复错误。
    // 因此这里必须保留旧快照，并把状态标记为 stale，等待下一轮轮询恢复。
    hostStore.markStale?.()
    return
  }

  if (hostStore.syncSnapshot) {
    hostStore.syncSnapshot(cloneSnapshot(readResult.snapshot), readResult.kind)
    return
  }

  hostStore.available = readResult.snapshot.available
  hostStore.docTitle = readResult.snapshot.docTitle
  hostStore.text = readResult.snapshot.text
  hostStore.updatedAt = readResult.snapshot.updatedAt

  if (readResult.kind === 'ready') {
    hostStore.markReady?.()
    return
  }

  hostStore.markNoDocument?.()
}

/**
 * 创建 WPS 宿主适配器。
 *
 * 当前阶段只做“前端本地轮询 + 本地缓存”：
 * - 不把正文推给后端
 * - 不接知识库 API
 * - 不接 SSE
 */
export function createWpsHostAdapter(explicitApi?: WpsApiLike): WpsHostAdapter {
  let snapshot: HostSnapshot = createUnavailableSnapshot()
  let pollingTimer: ReturnType<typeof setInterval> | null = null

  async function pollOnce(hostStore?: HostStoreWritable): Promise<HostSnapshot> {
    const readResult = readSnapshotFromApi(resolveWpsApi(explicitApi))

    // 关键点：读取异常时不更新内部快照，避免把上一份成功结果抹掉。
    if (readResult.kind !== 'read_error') {
      snapshot = readResult.snapshot
    }

    writeReadResultToHostStore(hostStore, readResult)
    return cloneSnapshot(snapshot)
  }

  function stopPolling() {
    if (!pollingTimer) {
      return
    }

    clearInterval(pollingTimer)
    pollingTimer = null
  }

  return {
    async startPolling(hostStore?: HostStoreWritable) {
      stopPolling()

      // 兼容 Task 4 既有测试：如果没有传 store，仍然保留“一次读取”的旧行为。
      if (!hostStore) {
        await pollOnce()
        return
      }

      hostStore.markPolling?.()
      await pollOnce(hostStore)

      pollingTimer = setInterval(() => {
        const readResult = readSnapshotFromApi(resolveWpsApi(explicitApi))

        // 关键点：读取异常时不更新内部快照，避免把上一份成功结果抹掉。
        if (readResult.kind !== 'read_error') {
          snapshot = readResult.snapshot
        }

        writeReadResultToHostStore(hostStore, readResult)
      }, WPS_POLLING_INTERVAL_MS)
    },

    stopPolling,

    pollOnce,

    getSnapshot() {
      return cloneSnapshot(snapshot)
    },
  }
}
