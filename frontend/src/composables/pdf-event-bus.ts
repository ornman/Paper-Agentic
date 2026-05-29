import type { InjectionKey } from 'vue'
import type { EventBus } from 'pdfjs-dist/web/pdf_viewer.mjs'

export const PDF_EVENT_BUS_KEY: InjectionKey<EventBus> = Symbol('pdfEventBus')
