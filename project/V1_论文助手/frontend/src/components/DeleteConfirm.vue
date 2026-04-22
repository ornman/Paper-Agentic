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
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.dialog {
  background: white;
  border-radius: 12px;
  padding: 24px;
  width: 320px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
}

.dialog-title {
  margin: 0 0 12px;
  font-size: 16px;
  font-weight: 600;
  color: #1a1a1a;
}

.dialog-body {
  margin: 0 0 20px;
  font-size: 14px;
  line-height: 1.6;
  color: #595959;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.btn-cancel {
  padding: 6px 16px;
  background: white;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 14px;
  color: #595959;
  cursor: pointer;
}

.btn-cancel:hover {
  border-color: #b3b3b3;
}

.btn-danger {
  padding: 6px 16px;
  background: #ff4d4f;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  color: white;
  cursor: pointer;
}

.btn-danger:hover:not(:disabled) {
  background: #e04345;
}

.btn-danger:disabled {
  background: #ffa39e;
  cursor: not-allowed;
}
</style>
