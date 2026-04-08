# Claude 配置 - 前端原型项目

> **项目状态**: 演示版（2026-03-23）
> **用途**: WPS 论文写作辅助工具的 UI 展示原型（纯前端，无后端）

---

## 项目定位

这是一个 **纯前端展示原型**，用于向客户演示界面效果：

- 不连接真实后端，所有数据都是模拟的
- 需要嵌入 WPS 侧边栏 TaskPane
- 界面风格：专业、简约、不像"AI 风格"
- **可独立运行** `wpsjs debug`，无需依赖 `.tools/wps-debug/`

---

## 目录结构

```
frontend-prototype/
├── manifest.xml       # WPS 插件清单
├── ribbon.xml         # 功能区按钮定义
├── main.js            # Ribbon 回调函数
├── index.html         # WPS 插件入口（加载 main.js）
├── app.html           # Vue 应用入口
├── src/               # Vue 源码
│   ├── main.ts
│   ├── App.vue
│   ├── components/
│   └── stores/
├── dist/              # 构建产物
│   ├── app.html       # TaskPane 内容
│   └── assets/
└── docs/              # 项目文档
```

---

## 快速启动

```bash
# 1. 构建（首次或修改后）
cd D:/同步/project/frontend-prototype
pnpm build

# 2. 启动调试
wpsjs debug

# 3. 在 WPS 中点击：论文助手 → 打开助手
```

---

## 开发流程

```bash
# 开发模式（浏览器预览）
pnpm dev

# 构建生产版本
pnpm build

# 启动 WPS 调试
wpsjs debug
```

---

## 设计决策（已锁定）

| 决策 | 结论 | 理由 |
|------|------|------|
| 整体风格 | DeepSeek 简约风 | 用户偏好，专业感 |
| 主题系统 | 4 主题 + CSS 变量 | 适应不同偏好 |
| 图标策略 | SVG 内联 | 可控、无依赖 |
| 布局结构 | Tab 切换 | 节省 TaskPane 空间 |
| WPS 集成 | Vite `base: './'` | 本地路径兼容 |
| 独立调试 | 自带 manifest.xml | 无需复制到 .tools/wps-debug |

详细决策记录见：`docs/71-decisions/决策-UI设计风格与主题系统.md`

---

## 技术栈

- Vue 3 + TypeScript
- Vite（`base: './'`）
- Pinia 状态管理
- 纯 CSS 变量（主题切换）
- 内联 SVG 图标
