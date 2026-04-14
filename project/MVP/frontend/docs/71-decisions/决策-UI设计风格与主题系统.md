# 决策 - UI 设计风格与主题系统

> **创建日期**: 2026-03-23
> **状态**: 决策记录，已冻结
> **决策日期**: 2026-03-23

---

## 1. 背景与问题

### 1.1 项目定位

这是一个 **纯前端展示原型**，用于向客户演示 WPS 论文写作辅助工具的界面效果。

**核心约束**：
- 不连接真实后端，所有数据都是模拟的
- 需要嵌入 WPS 侧边栏 TaskPane
- 界面要看起来专业，不像"AI 风格"

### 1.2 设计挑战

| 挑战 | 说明 |
|------|------|
| **AI 味太重** | 初始设计使用了大量 emoji，看起来像聊天机器人 |
| **风格单一** | 需要支持多种主题风格，适应不同用户偏好 |
| **WPS 集成** | 需要嵌入 WPS 侧边栏，路径配置有特殊性 |

---

## 2. 决策内容

### 2.1 整体风格定位

**决策**: 采用 **DeepSeek 简约风格** 作为默认主题

**理由**:
1. 用户偏好 DeepSeek 的极简黑白灰风格
2. 简约风格更专业，不像"AI 助手"
3. 适合论文写作场景（学术、严谨）

**对比**:
| 风格 | 特点 | 适用场景 |
|------|------|----------|
| DeepSeek 简约 | 极简黑白灰，无装饰 | 专业、学术 ✅ |
| 现代聊天风格 | 渐变、圆角、气泡 | 消费级应用 ❌ |
| Copilot 风格 | 紫色、玻璃拟态 | AI 助手 ❌ |

### 2.2 主题系统设计

**决策**: 实现 4 种主题风格，通过 CSS 变量切换

**主题列表**:
| ID | 名称 | 主色调 | 适用场景 |
|----|------|--------|----------|
| `deepseek` | DeepSeek 简约 | `#5D5D5D` 灰 | 默认，专业场景 |
| `academic` | 学术专业 | `#0D9488` Teal | 学术论文 |
| `notion` | Notion 清新 | `#2EAADC` 蓝 | 轻松阅读 |
| `dark` | 暗夜模式 | `#10A37F` 绿 | 夜间使用 |

**实现方式**:
```typescript
// CSS 变量映射
const cssVarMap = {
  primary: '--primary',
  bgMain: '--bg-main',
  textPrimary: '--text-primary',
  // ...
}

// 切换主题时动态更新 CSS 变量
Object.entries(theme.colors).forEach(([key, value]) => {
  const cssKey = '--' + key.replace(/([A-Z])/g, '-$1').toLowerCase()
  document.documentElement.style.setProperty(cssKey, value)
})
```

### 2.3 图标策略

**决策**: 使用 SVG 图标，完全移除 emoji

**理由**:
1. Emoji 在不同系统上显示不一致
2. Emoji 看起来不专业，像"玩具"
3. SVG 图标可以精确控制颜色和大小

**图标来源**: 内联 SVG，viewBox 统一为 24x24

### 2.4 布局结构

**决策**: 采用 Tab 切换式布局，非侧边栏导航

**结构**:
```
┌─────────────────────────┐
│ [导入] [对话] [设置]    │  <- TabBar
├─────────────────────────┤
│                         │
│      TabContent         │  <- 内容区
│                         │
└─────────────────────────┘
```

**理由**:
1. WPS TaskPane 宽度有限（400px），侧边栏导航会占用空间
2. Tab 切换更符合工具型应用的交互模式
3. 三个功能模块相对独立，不需要频繁切换

### 2.5 WPS 集成方案

**决策**: 使用 WPSJS TaskPane API，Vite 构建使用相对路径

**关键配置**:
```typescript
// vite.config.ts
export default defineConfig({
  base: './',  // 关键！使用相对路径
  // ...
})
```

**理由**:
- WPS TaskPane 加载本地 HTML，绝对路径 `/assets/...` 会 404
- 相对路径 `./assets/...` 才能正确加载资源

---

## 3. 技术选型

| 技术 | 选择 | 理由 |
|------|------|------|
| 框架 | Vue 3 + TypeScript | 轻量、响应式、类型安全 |
| 构建 | Vite | 快速、支持 Vue SFC |
| 状态 | Pinia | 简单、TypeScript 友好 |
| 样式 | 纯 CSS 变量 | 无需预处理器，主题切换简单 |
| 图标 | 内联 SVG | 可控、无依赖 |

---

## 4. 影响范围

| 模块 | 影响 |
|------|------|
| `themeStore.ts` | 主题状态管理 |
| `style.css` | CSS 变量定义 |
| `SettingsPage.vue` | 主题切换 UI |
| `vite.config.ts` | 相对路径配置 |
| WPS 插件 | TaskPane 集成 |

---

## 5. 后续演进（未来版本）

以下功能 **不在当前原型范围内**，但值得记录：

1. **自定义主题**: 允许用户自定义主色调
2. **主题持久化**: 保存到 localStorage
3. **跟随系统**: 跟随系统深色/浅色模式
4. **高对比度模式**: 无障碍支持

---

## 6. 参考资料

- [UI-UX-Pro-Max](https://github.com/AnoyiX/ui-ux-pro-max) - 设计系统生成工具
- [DeepSeek 官网](https://deepseek.com) - 简约风格参考
- [WPSJS 开发文档](https://open.wps.cn) - TaskPane API
