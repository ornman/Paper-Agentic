<script setup lang="ts">
const props = defineProps<{
  writtenContent: string
  selectedText: string
  promptText: string
}>()

function createPreview(text: string, emptyLabel: string): string {
  const normalized = text.trim().replace(/\s+/g, ' ')
  if (!normalized) {
    return emptyLabel
  }

  if (normalized.length <= 72) {
    return normalized
  }

  return `${normalized.slice(0, 72)}…`
}
</script>

<template>
  <section class="context-preview" data-testid="context-preview" aria-label="上下文调试预览">
    <div class="context-item">
      <p class="context-label">正文</p>
      <p class="context-value">{{ createPreview(props.writtenContent, '当前还没有读取到正文') }}</p>
    </div>

    <div class="context-item">
      <p class="context-label">选区</p>
      <p class="context-value">{{ createPreview(props.selectedText, '当前没有选中文本') }}</p>
    </div>

    <div class="context-item">
      <p class="context-label">提示词</p>
      <p class="context-value">{{ createPreview(props.promptText, '当前还没有输入提示词') }}</p>
    </div>
  </section>
</template>

<style scoped>
.context-preview {
  display: grid;
  gap: 12px;
  padding: 18px 20px;
  border: 1px solid rgba(216, 209, 198, 0.9);
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.82);
}

.context-item {
  display: grid;
  gap: 4px;
}

.context-label {
  color: var(--color-text-secondary);
  font-size: 11px;
  line-height: 1;
}

.context-value {
  color: var(--color-text-primary);
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
}
</style>
