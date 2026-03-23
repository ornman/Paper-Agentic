import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: './',  // 使用相对路径，兼容 WPS 插件环境
  server: {
    port: 3000
  }
})
