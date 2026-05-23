// 宿主快照：描述当前 WPS 文档在前端中的最小可观察状态。
// Task 1 只定义类型，不接入真实轮询逻辑。
export interface HostSnapshot {
  available: boolean
  docTitle: string
  text: string
  updatedAt: string | null
}
