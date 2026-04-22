<template>
  <div v-if="visible" class="overlay" @click.self="$emit('cancel')">
    <div class="dialog">
      <h3 class="dialog-title">确认删除？</h3>
      <p class="dialog-body">
        将删除《{{ paperTitle }}》的所有向量数据（{{ chunkCount }} 个文本块），此操作不可恢复。
      </p>
      <div class="dialog-actions">
        <button class="btn-cancel" @click="$emit('cancel')">取消</button>
        <button class="btn-danger" @click="$emit('confirm')" :disabled="deleting">
          {{ deleting ? '删除中...' : '确认删除' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  visible: boolean
  paperTitle: string
  chunkCount: number
  deleting: boolean
}>()

defineEmits<{
  confirm: []
  cancel: []
}>()
</script>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(26, 25, 21, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.dialog {
  background: var(--claude-bg-card);
  border-radius: var(--claude-radius-lg);
  padding: var(--claude-spacing-lg);
  width: 320px;
  box-shadow: var(--claude-shadow-lg);
}

.dialog-title {
  margin: 0 0 var(--claude-spacing-md);
  font-size: 16px;
  font-weight: 600;
  color: var(--claude-text-primary);
}

.dialog-body {
  margin: 0 0 var(--claude-spacing-lg);
  font-size: 14px;
  line-height: 1.6;
  color: var(--claude-text-secondary);
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--claude-spacing-sm);
}

.btn-cancel {
  padding: var(--claude-spacing-sm) var(--claude-spacing-md);
  background: var(--claude-bg-card);
  border: 1px solid var(--claude-border);
  border-radius: var(--claude-radius-md);
  font-size: 14px;
  color: var(--claude-text-secondary);
  cursor: pointer;
}

.btn-cancel:hover {
  border-color: var(--claude-text-muted);
  background: var(--claude-bg-muted);
}

.btn-danger {
  padding: var(--claude-spacing-sm) var(--claude-spacing-md);
  background: var(--claude-error);
  border: none;
  border-radius: var(--claude-radius-md);
  font-size: 14px;
  color: white;
  cursor: pointer;
}

.btn-danger:hover:not(:disabled) {
  background: #A83C3C;
}

.btn-danger:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
