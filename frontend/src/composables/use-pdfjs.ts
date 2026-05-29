// frontend/src/composables/use-pdfjs.ts
import * as pdfjsLib from 'pdfjs-dist'

let initialized = false

function initWorker() {
  if (initialized) return
  initialized = true

  // pdfjs-dist/web/pdf_viewer.mjs 在顶层解构 globalThis.pdfjsLib，
  // 必须在任何 pdf_viewer 导入之前设置
  if (typeof globalThis !== 'undefined' && !(globalThis as Record<string, unknown>).pdfjsLib) {
    (globalThis as Record<string, unknown>).pdfjsLib = pdfjsLib
  }

  try {
    // Dev 模式：使用 import.meta.url 加载 worker
    if (typeof import.meta !== 'undefined' && import.meta.url) {
      pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
        'pdfjs-dist/build/pdf.worker.min.mjs',
        import.meta.url,
      ).toString()
    } else {
      // WPS IIFE 构建：假 worker，主线程运行
      pdfjsLib.GlobalWorkerOptions.workerSrc = ''
    }
  } catch {
    pdfjsLib.GlobalWorkerOptions.workerSrc = ''
  }
}

export function usePdfjs() {
  initWorker()
  return {
    lib: pdfjsLib,
    cMapOptions: {
      cMapUrl: '/cmaps/',
      cMapPacked: true,
    } as const,
  }
}
