# WPS 论文写作辅助工具 - UI 原型

> 状态：已冻结（2026-03-23）
> 用途：前端展示原型，给客户演示用

## 快速启动

### 1. 启动 WPS 插件

```bash
cd D:/同步/.tools/wps-debug/test-plugin
wpsjs debug
```

### 2. 在 WPS 中打开

1. 点击 **测试插件** 选项卡
2. 点击 **论文助手 (UI原型)** 按钮
3. 右侧侧边栏会显示 Vue 界面

## 功能演示

### 三个标签页

| 标签 | 功能 |
|------|------|
| **导入** | PDF 路径输入、导入进度动画、已导入文档列表 |
| **对话** | 会话切换、消息发送、流式响应、来源卡片展示 |
| **设置** | 主题风格切换、服务配置、LLM 供应商选择 |

### 四种主题风格

| 风格 | 特点 |
|------|------|
| **DeepSeek 简约** | 极简黑白灰，无多余装饰（默认） |
| **学术专业** | Teal 青绿色，学术感 |
| **Notion 清新** | 柔和白色，清新舒适 |
| **暗夜模式** | 深色主题，护眼 |

## 项目结构

```
D:/同步/project/frontend-prototype/
├── src/
│   ├── components/
│   │   ├── layout/         # TabBar, TabContent
│   │   ├── ingest/         # 导入页面
│   │   ├── chat/           # 对话页面
│   │   └── settings/       # 设置页面
│   ├── stores/
│   │   ├── mockStore.ts    # 模拟数据
│   │   └── themeStore.ts   # 主题切换
│   ├── App.vue
│   ├── main.ts
│   └── style.css
├── package.json
├── vite.config.ts
└── README.md
```

## 修改后重新部署

如果修改了源代码，需要重新构建并部署：

```bash
cd D:/同步/project/frontend-prototype
pnpm build
rm -rf D:/同步/.tools/wps-debug/test-plugin/vue-app/*
cp -r dist/* D:/同步/.tools/wps-debug/test-plugin/vue-app/
```

然后重启 `wpsjs debug`。

## 技术栈

- **Vue 3** + TypeScript
- **Vite** 构建工具
- **Pinia** 状态管理
- **纯 CSS** 样式（CSS 变量实现主题切换）

## 注意事项

1. **这是纯前端原型**，不连接真实后端
2. 所有数据都是模拟的，存储在内存中
3. 刷新页面后数据会重置
4. WPS 插件需要 `wpsjs` 工具支持

## 相关文档

- MVP 技术文档：`D:/同步/project/docs/mvp/26-3-20：MVP技术文档.md`
- WPS 调试系统：`D:/同步/.tools/wps-debug/`
