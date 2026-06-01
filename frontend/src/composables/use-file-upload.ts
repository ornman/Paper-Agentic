/**
 * 触发浏览器文件选择对话框。
 * 返回 triggerUpload 函数，点击后弹出文件选择器，选择后回调 onFiles。
 */
export function useFileUpload(opts: {
  accept: string
  multiple?: boolean
  onFiles: (files: File[]) => void | Promise<void>
}) {
  function triggerUpload() {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = opts.accept
    input.multiple = opts.multiple ?? false
    input.onchange = async () => {
      const files = input.files
      if (!files || files.length === 0) return
      await opts.onFiles(Array.from(files))
    }
    input.click()
  }

  return { triggerUpload }
}
