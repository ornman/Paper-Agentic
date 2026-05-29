// pdfjs-dist/web/pdf_viewer.mjs 在模块顶层解构 globalThis.pdfjsLib，
// 必须在所有其他 import 之前设置，否则应用启动即崩溃
import * as _pdfjsLib from 'pdfjs-dist'
;(globalThis as Record<string, unknown>).pdfjsLib = _pdfjsLib

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { setupGlobalErrorCapture } from './composables/logger'
import './style.css'

setupGlobalErrorCapture()

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.mount('#app')
