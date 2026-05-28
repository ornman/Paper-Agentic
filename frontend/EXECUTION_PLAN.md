# UI 细化执行计划

> 生成时间: 2026-05-28
> 状态: **已完成**（2026-05-29 验证通过）

## 任务 1：文献选中态柔化

**文件**: `src/components/LibraryPanel.vue`

**改动**:
- `.library-item` 添加 `transition: background 0.25s ease, box-shadow 0.25s ease`
- `.library-item--selected` 改为:
  ```css
  background: var(--color-accent-soft);
  box-shadow: inset 0 0 0 1.5px color-mix(in srgb, var(--color-accent) 25%, transparent);
  ```
- `.library-item--selected:hover` 保持 `background: var(--color-accent-soft)` 不变（选中后 hover 不变色）

**位置**: 行 322-342（CSS 部分）

---

## 任务 2：行内引用改进

**文件**: `src/components/AIMessage.vue`

### 2a. 改写 `renderParagraphWithCitations()` 逻辑

- 不再匹配论文标题片段
- 新策略：在句末标点（`。！？；.!?`）之后、或段落末尾，插入引用标记
- 分配逻辑：按段落出现顺序轮流分配 source，每段最多 2 个引用标记
- 标记 HTML: `<sup class="cite-marker" data-source-id="...">[N]</sup>`（格式不变，样式改）

### 2b. 样式改进

`.cite-marker` CSS 改为:
```css
.cite-marker {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  vertical-align: super;
  font-size: 0.65em;
  line-height: 1;
  min-width: 1.2em;
  padding: 0.1em 0.3em;
  margin-left: 2px;
  color: #fff;
  background: var(--color-accent);
  border-radius: 999px;
  cursor: pointer;
  transition: opacity 0.15s, transform 0.15s;
}

.cite-marker:hover {
  opacity: 0.8;
  transform: scale(1.1);
}
```

### 2c. 底部引用来源区

**保持不变**，继续显示 `sources-section` 中的 badge 列表。

**位置**: 行 134-166（逻辑）、行 442-457（CSS）

---

## 任务 3：新建对话 SVG 替换

### 3a. 复制 SVG 文件

```
源: E:\DOWN\fluent--chat-add-24-regular.svg
目标: src/assets/icons/chat-add.svg
```

### 3b. 修改 TopNavBar.vue

- 添加 import: `import iconChatAdd from '../assets/icons/chat-add.svg?raw'`
- 行 16-22: 替换内联 SVG 为 `<span class="icon-svg" v-html="iconChatAdd" />`
- `.icon-button .icon-svg` 样式: `width: 20px; height: 20px; color: currentColor`（SVG 用 fill="currentColor" 自动适配主题）

**位置**: `src/components/TopNavBar.vue` 行 16-22（模板）、行 42（script）

---

## 执行顺序

1. 任务 1（LibraryPanel 选中态） — 改动最小，先验证编译
2. 任务 3（SVG 替换） — 独立文件，不依赖其他改动
3. 任务 2（行内引用） — 逻辑最复杂，放最后
4. 全部完成后 `npm run build` 验证编译通过
5. 刷新 `http://localhost:3905/app.html?demo` 验证视觉效果
