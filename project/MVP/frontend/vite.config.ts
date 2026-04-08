/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  base: './', // 使用相对路径，兼容 WPS 插件环境
  server: {
    port: 3000,
  },
  test: {
    environment: 'jsdom',
  },
  build: {
    rollupOptions: {
      input: {
        // 正式 Vue 应用入口。
        app: resolve(__dirname, 'app.html'),

        // WPS TaskPane 的静态壳入口。
        // 这样构建产物中也会保留一个可直接打开的 TaskPane 页面，
        // 便于宿主环境和本地构建产物使用同一套入口约定。
        taskpane: resolve(__dirname, 'wps-plugin/taskpane.html'),
      },
    },
  },
})
