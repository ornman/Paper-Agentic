<script lang="ts">
const WINDOWS_ABSOLUTE_PDF_PATH_PATTERN = /^[a-zA-Z]:[\\/].+\.pdf$/i

export interface PdfPathValidationResult {
  ok: boolean
  message: string | null
  normalizedPath: string | null
}

/**
 * 校验 PDF 路径输入。
 *
 * 第一版只接受本机绝对路径，原因不是“技术上只能这样”，
 * 而是当前产品语义已经锁定为“把本地 PDF 交给后端导入链路”。
 * 因此这里要先在前端挡住三类明显错误：
 * 1. 空字符串
 * 2. 不是本地绝对路径（例如 URL）
 * 3. 不是 .pdf 文件
 */
export function validatePdfPathInput(rawInput: string): PdfPathValidationResult {
  const normalizedPath = rawInput.trim()

  if (!normalizedPath) {
    return {
      ok: false,
      message: '输入有误',
      normalizedPath: null,
    }
  }

  if (/^[a-z]+:\/\//i.test(normalizedPath)) {
    return {
      ok: false,
      message: '输入有误',
      normalizedPath: null,
    }
  }

  if (!WINDOWS_ABSOLUTE_PDF_PATH_PATTERN.test(normalizedPath)) {
    return {
      ok: false,
      message: '输入有误',
      normalizedPath: null,
    }
  }

  return {
    ok: true,
    message: null,
    normalizedPath,
  }
}
</script>

<script setup lang="ts">
import { getActivePinia } from 'pinia'
import { computed, ref } from 'vue'
import { useLibraryStore } from '../../stores/library'

const activePinia = getActivePinia()
const libraryStore = activePinia ? useLibraryStore(activePinia) : null

const pdfPathInput = ref('')
const localMessage = ref<string | null>(null)

const isImporting = computed(() => libraryStore?.status === 'importing')
const visibleMessage = computed(() => localMessage.value ?? libraryStore?.errorMessage ?? null)

/**
 * 输入变化时先清掉旧错误，避免用户已经改正输入了，界面还停留在上一轮失败提示。
 */
function handleInput() {
  localMessage.value = null
  libraryStore?.clearError()
}

/**
 * 提交导入。
 *
 * 这里坚持“先前端校验，再碰后端”：
 * - 输入明显错误时，直接提示“输入有误”
 * - 只有通过最小语义校验后，才调用 store 进入导入流程
 */
async function handleSubmit() {
  const validationResult = validatePdfPathInput(pdfPathInput.value)

  if (!validationResult.ok) {
    localMessage.value = validationResult.message
    libraryStore?.markError('输入有误')
    return
  }

  localMessage.value = null

  if (!libraryStore) {
    return
  }

  await libraryStore.importPdf(validationResult.normalizedPath as string)

  if (libraryStore.status !== 'error') {
    pdfPathInput.value = ''
  }
}
</script>

<template>
  <div class="import-pdf-button" data-testid="import-pdf-button">
    <div class="input-row">
      <input
        :value="pdfPathInput"
        class="path-input"
        data-testid="pdf-path-input"
        type="text"
        placeholder="输入本地 PDF 路径，如：D:/papers/example.pdf"
        :disabled="isImporting"
        @input="handleInput(); pdfPathInput = ($event.target as HTMLInputElement).value"
      />

      <button
        class="submit-button"
        data-testid="pdf-import-submit"
        type="button"
        :disabled="isImporting"
        @click="handleSubmit"
      >
        {{ isImporting ? '导入中…' : '导入 PDF' }}
      </button>
    </div>

    <p v-if="visibleMessage" class="message-text" data-testid="pdf-import-message">
      {{ visibleMessage }}
    </p>
  </div>
</template>

<style scoped>
.import-pdf-button {
  width: 100%;
}

.input-row {
  display: flex;
  gap: var(--space-2);
  align-items: center;
  width: 100%;
}

.path-input {
  flex: 1;
  min-width: 0;
  min-height: 32px;
  padding: 0 10px;
  border: 1px solid var(--color-border-subtle);
  border-radius: 10px;
  background: var(--color-surface-base);
  color: var(--color-text-primary);
  font-size: var(--font-size-caption);
}

.path-input:focus {
  outline: none;
  border-color: var(--color-accent);
}

.submit-button {
  flex-shrink: 0;
  min-height: 32px;
  padding: 0 10px;
  border: 1px solid var(--color-border-subtle);
  border-radius: 10px;
  background: var(--color-surface-base);
  color: var(--color-text-primary);
  cursor: pointer;
}

.submit-button:disabled,
.path-input:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.message-text {
  margin-top: 6px;
  font-size: var(--font-size-caption);
  color: #b42318;
}
</style>
