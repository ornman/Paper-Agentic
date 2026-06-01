import { ref, watch, nextTick, type WatchSource } from 'vue'

/**
 * 自动滚动到底部。
 * 绑定到一个 template ref 元素，监听指定 trigger 的变化自动 scroll。
 */
export function useAutoScroll(...triggers: WatchSource<unknown>[]) {
  const containerRef = ref<HTMLElement>()

  function scrollToBottom() {
    nextTick(() => {
      const el = containerRef.value
      if (el) el.scrollTop = el.scrollHeight
    })
  }

  for (const trigger of triggers) {
    watch(trigger, scrollToBottom)
  }

  return { containerRef, scrollToBottom }
}
