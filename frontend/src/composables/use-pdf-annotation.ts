// frontend/src/composables/use-pdf-annotation.ts
import type { PDFDocumentProxy, PDFPageProxy, PageViewport } from 'pdfjs-dist'

const SAFE_PROTOCOLS = new Set(['http:', 'https:', 'mailto:', 'ftp:'])

function isSafeUrl(url: string): boolean {
  if (url.startsWith('#')) return true
  try {
    const parsed = new URL(url, window.location.href)
    return SAFE_PROTOCOLS.has(parsed.protocol)
  } catch {
    return false
  }
}

/**
 * Duck-typed linkService that satisfies pdfjs AnnotationLayer's expectations.
 * Only the methods actually called by LinkAnnotationElement are implemented.
 */
interface LinkService {
  getDestinationHash(dest: string | unknown[]): string
  getAnchorUrl(anchor: string): string
  goToDestination(dest: string | unknown[]): Promise<void>
  executeNamedAction(action: string): void
  executeSetOCGState(action: unknown): Promise<void>
  addLinkAttributes(link: HTMLAnchorElement, url: string, newWindow?: boolean): void
}

export interface AnnotationAdapter {
  linkService: LinkService
  pdfDocument: PDFDocumentProxy | null
  setDocument(doc: PDFDocumentProxy | null): void
  renderAnnotations(
    pageProxy: PDFPageProxy,
    viewport: PageViewport,
    container: HTMLDivElement,
  ): Promise<void>
}

/**
 * Create an AnnotationAdapter for rendering clickable links in PDF pages.
 *
 * @param scrollToPage - Callback to scroll the viewer to a given page number
 */
export function usePdfAnnotation(scrollToPage: (pageNum: number) => void): {
  adapter: AnnotationAdapter
} {
  let pdfDocument: PDFDocumentProxy | null = null

  const linkService: LinkService = {
    getDestinationHash(dest: string | unknown[]): string {
      if (typeof dest === 'string') {
        return `#dest=${dest}`
      }
      return '#'
    },

    getAnchorUrl(anchor: string): string {
      return anchor
    },

    async goToDestination(dest: string | unknown[]): Promise<void> {
      if (!pdfDocument) return

      try {
        let resolvedDest: unknown[] | string | null = dest as unknown[] | string
        // Named destination: resolve to explicit dest array
        if (typeof dest === 'string') {
          resolvedDest = await pdfDocument.getDestination(dest)
        }

        if (Array.isArray(resolvedDest) && resolvedDest.length > 0) {
          // dest[0] is a page ref object; use getPageIndex to get 0-based index
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const pageIdx = await pdfDocument.getPageIndex(resolvedDest[0] as any)
          scrollToPage(pageIdx + 1)
        }
      } catch {
        // Destination resolution failed — no-op
      }
    },

    executeNamedAction(action: string): void {
      // Named actions like NextPage, PrevPage, GoBack, etc.
      // Best-effort mapping for the most common ones
      switch (action) {
        case 'NextPage':
          // Cannot determine current page here without more context; no-op
          break
        case 'PrevPage':
          break
        default:
          break
      }
    },

    async executeSetOCGState(_action: unknown): Promise<void> {
      // Optional Content Group state changes — no-op for our viewer
    },

    addLinkAttributes(link: HTMLAnchorElement, url: string, newWindow?: boolean): void {
      if (!isSafeUrl(url)) {
        link.removeAttribute('href')
        link.onclick = (event: MouseEvent) => { event.preventDefault() }
        return
      }
      link.href = url
      link.rel = 'noopener noreferrer nofollow'
      if (newWindow) {
        link.target = '_blank'
        link.onclick = (event: MouseEvent) => {
          event.preventDefault()
          window.open(url, '_blank', 'noopener,noreferrer')
        }
      } else {
        link.target = ''
        link.onclick = (event: MouseEvent) => {
          event.preventDefault()
          window.location.href = url
        }
      }
    },
  }

  function setDocument(doc: PDFDocumentProxy | null): void {
    pdfDocument = doc
  }

  async function renderAnnotations(
    pageProxy: PDFPageProxy,
    viewport: PageViewport,
    container: HTMLDivElement,
  ): Promise<void> {
    // Clear previous annotation layer content
    container.innerHTML = ''

    let AnnotationLayerClass: typeof import('pdfjs-dist').AnnotationLayer | null = null
    try {
      const module = await import('pdfjs-dist')
      AnnotationLayerClass = module.AnnotationLayer
    } catch {
      // WPS compatibility: if import fails, silently skip annotation rendering
      return
    }

    if (!AnnotationLayerClass) return

    let annotations: unknown[]
    try {
      annotations = await pageProxy.getAnnotations()
    } catch {
      // Some pages may not support annotations
      return
    }

    // Only proceed if there are annotations to render
    if (!annotations || annotations.length === 0) return

    // The constructor uses duck typing internally — cast via unknown
    const annotationLayer = new AnnotationLayerClass({
      div: container,
      page: pageProxy,
      viewport,
      linkService: linkService as unknown,
      annotationStorage: undefined,
      accessibilityManager: undefined,
      annotationCanvasMap: undefined,
      annotationEditorUIManager: undefined,
      structTreeLayer: undefined,
      commentManager: undefined,
    })

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const ls = linkService as any

    await annotationLayer.render({
      annotations,
      viewport,
      div: container,
      page: pageProxy,
      linkService: ls,
      renderForms: false,
      imageResourcesPath: '',
      enableScripting: false,
    })
  }

  const adapter: AnnotationAdapter = {
    linkService,
    get pdfDocument() {
      return pdfDocument
    },
    setDocument,
    renderAnnotations,
  }

  return { adapter }
}
