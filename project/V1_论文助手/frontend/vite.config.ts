import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  base: './', // WPS 插件使用相对路径
  server: {
    port: 3000,
  },
  build: {
    rollupOptions: {
      input: {
        app: resolve(__dirname, 'app.html'),
        taskpane: resolve(__dirname, 'wps-plugin/taskpane.html'),
      },
    },
  },
})
