<template>
  <Teleport to="body">
    <Transition name="confirm-fade">
      <div v-if="visible" class="confirm-overlay" @click.self="emit('cancel')">
        <div class="confirm-dialog">
          <p class="confirm-message">{{ count > 1 ? `确定要删除选中的 ${count} 篇论文吗？` : '确定要删除这篇论文吗？' }}</p>
          <p v-if="warning" class="confirm-warning">{{ warning }}</p>
          <p class="confirm-title">{{ title }}</p>
          <label class="confirm-skip">
            <input type="checkbox" :checked="skipConfirm" @change="emit('update:skipConfirm', ($event.target as HTMLInputElement).checked)" />
            <span>本次对话不再提示</span>
          </label>
          <div class="confirm-actions">
            <button class="confirm-btn confirm-btn--cancel" type="button" @click="emit('cancel')">取消</button>
            <button class="confirm-btn confirm-btn--danger" type="button" @click="emit('confirm')">删除</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
defineProps<{
  visible: boolean
  title: string
  count: number
  skipConfirm: boolean
  warning?: string
}>()

const emit = defineEmits<{
  (e: 'confirm'): void
  (e: 'cancel'): void
  (e: 'update:skipConfirm', value: boolean): void
}>()
</script>

<style scoped>
.confirm-overlay {
  position: fixed;
  inset: 0;
  z-index: 300;
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.confirm-dialog {
  width: 280px;
  background: var(--color-surface-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.confirm-message {
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--color-text-primary);
  margin: 0;
}

.confirm-warning {
  font-size: 12px;
  color: var(--color-error, #c53030);
  margin: 0;
  opacity: 0.8;
}

.confirm-title {
  font-size: 12px;
  color: var(--color-text-muted);
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.confirm-skip {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 12px;
  color: var(--color-text-secondary);
  cursor: pointer;
  user-select: none;
}

.confirm-skip input {
  accent-color: var(--color-accent);
  cursor: pointer;
}

.confirm-actions {
  display: flex;
  gap: var(--space-2);
  justify-content: flex-end;
  margin-top: var(--space-1);
}

.confirm-btn {
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  font-weight: 500;
  cursor: pointer;
  border: 1px solid var(--color-border-subtle);
  transition: background 0.15s ease, border-color 0.15s ease;
}

.confirm-btn--cancel {
  background: transparent;
  color: var(--color-text-secondary);
}

.confirm-btn--cancel:hover {
  background: var(--color-surface-muted);
}

.confirm-btn--danger {
  background: var(--color-error, #c53030);
  color: #fff;
  border-color: var(--color-error, #c53030);
}

.confirm-btn--danger:hover {
  opacity: 0.9;
}

.confirm-fade-enter-active,
.confirm-fade-leave-active {
  transition: opacity 0.2s ease;
}

.confirm-fade-enter-from,
.confirm-fade-leave-to {
  opacity: 0;
}
</style>
