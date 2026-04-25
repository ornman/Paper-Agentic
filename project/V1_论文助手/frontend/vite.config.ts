import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import { copyFile, mkdir, writeFile, readFile, readdir } from 'fs/promises'

/**
 * 内联插件：构建后组装 WPS 插件文件到 dist/
 *
 * 关键策略：
 *   1. 将 taskpane 的 JS/CSS 内联到 HTML 中（IIFE 包裹）
 *      → 避免 WPS 内嵌浏览器对 ES Module 的兼容性问题
 *   2. app.html 保持外部引用（独立浏览器入口）
 *   3. package.json 添加 addonType 让 wpsjs debug 正确识别
 */
function assembleWpsPlugin() {
  const root = resolve(__dirname)
  const outDir = resolve(root, 'dist')

  // package.json — 让 wpsjs debug 识别插件（addonType 必须在顶层）
  const pkgJson = JSON.stringify({
    name: 'AIForScience',
    addonType: 'wps',
    version: '1.0.0',
    scripts: { start: 'wpsjs debug' },
    wpsAddon: {
      type: 'wps',
      name: 'AIForScience',
      version: '1.0.0',
    },
    debug: true,
  }, null, 2)

  // manifest.xml — 根目录引用
  const manifest = `<?xml version="1.0" encoding="UTF-8"?>
<oaddin xmlns="http://www.wps.cn/office/addins/1.0">
    <id>com.aiforscience.assistant</id>
    <name>AIForScience</name>
    <version>1.0.0</version>
    <provider>Thesis Assistant Team</provider>
    <description>基于 RAG 的学术论文写作辅助工具</description>
    <defaultLocale>zh-CN</defaultLocale>
    <hosts>
        <host name="wps" />
    </hosts>
    <resources>
        <ribbon>ribbon.xml</ribbon>
        <page>index.html</page>
    </resources>
</oaddin>`

  // index.html — 宿主入口
  const indexHtml = `<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>AIForScience</title></head>
<body><script src="main.js"></script></body>
</html>`

  return {
    name: 'assemble-wps-plugin',
    async closeBundle() {
      // 确保目录存在
      await mkdir(outDir, { recursive: true })

      // 写入根目录文件
      await writeFile(resolve(outDir, 'package.json'), pkgJson, 'utf-8')
      await writeFile(resolve(outDir, 'manifest.xml'), manifest, 'utf-8')
      await writeFile(resolve(outDir, 'index.html'), indexHtml, 'utf-8')

      // 从源目录复制 ribbon.xml 和 main.js 到根
      await copyFile(
        resolve(root, 'wps-plugin/ribbon.xml'),
        resolve(outDir, 'ribbon.xml'),
      )
      await copyFile(
        resolve(root, 'wps-plugin/main.js'),
        resolve(outDir, 'main.js'),
      )

      // ─── 内联构建产物到 taskpane.html ───
      const assetsDir = resolve(outDir, 'assets')
      let jsContent = ''
      let cssContent = ''

      try {
        const files = await readdir(assetsDir)
        for (const f of files) {
          const fullPath = resolve(assetsDir, f)
          if (f.endsWith('.js')) {
            jsContent += await readFile(fullPath, 'utf-8')
          } else if (f.endsWith('.css')) {
            cssContent += await readFile(fullPath, 'utf-8')
          }
        }
      } catch {
        // assets 目录可能不存在（构建失败时）
      }

      if (!jsContent) {
        console.warn('[assembleWpsPlugin] 未找到构建产物 JS，跳过 taskpane 内联')
        return
      }

      // 生成自包含的 taskpane.html（IIFE 包裹 JS，避免 ES Module 问题）
      const taskpaneHtml = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>论文写作助手 V1</title>
  <style>${cssContent}</style>
</head>
<body>
  <div id="app"></div>
  <script>
  // IIFE 包裹：将 ESM 代码隔离在函数作用域内
  (function() {
    "use strict";
    ${jsContent}
  })();
  </script>
</body>
</html>`

      await mkdir(resolve(outDir, 'wps-plugin'), { recursive: true })
      await writeFile(
        resolve(outDir, 'wps-plugin/taskpane.html'),
        taskpaneHtml,
        'utf-8',
      )

      console.log('[assembleWpsPlugin] taskpane.html 已内联生成（IIFE 模式）')
    },
  }
}

export default defineConfig({
  plugins: [vue(), assembleWpsPlugin()],
  base: './',
  server: {
    port: 3893,
    strictPort: true,
    host: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
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
