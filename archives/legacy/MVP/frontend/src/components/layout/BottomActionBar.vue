<script setup lang="ts">
import { getActivePinia } from 'pinia'
import { computed, ref, watch } from 'vue'
import { useConversationStore } from '../../stores/conversation'
import { useHostStore } from '../../stores/host'

const activePinia = getActivePinia()
const conversationStore = activePinia ? useConversationStore(activePinia) : null
const hostStore = activePinia ? useHostStore(activePinia) : null
const userPrompt = ref('')
const thinkingEnabled = ref(true)
const searchEnabled = ref(true)

watch(
  userPrompt,
  (value) => {
    conversationStore?.setPromptContext(value)
  },
  { immediate: true },
)

const isRequestInFlight = computed(
  () => conversationStore?.status === 'requesting' || conversationStore?.status === 'streaming',
)

const hasTypedPrompt = computed(() => userPrompt.value.trim().length > 0)

const isPrimaryActionDisabled = computed(() => {
  if (isRequestInFlight.value || !conversationStore) {
    return true
  }

  return !hasTypedPrompt.value
})

async function handlePrimaryAction() {
  if (!conversationStore || isPrimaryActionDisabled.value) {
    return
  }

  const prompt = userPrompt.value.trim()
  userPrompt.value = ''

  await conversationStore.sendPrompt({
    session_id: conversationStore.sessionId,
    query: prompt,
    context: {
      written_content: hostStore?.text ?? '',
      selected_text: conversationStore.selectionContext,
      prompt: conversationStore.promptContext,
    },
  })
}

async function handleComposerKeydown(event: KeyboardEvent) {
  const nativeEvent = event as KeyboardEvent & { isComposing?: boolean; keyCode?: number }
  if (nativeEvent.isComposing || nativeEvent.keyCode === 229) {
    return
  }

  if (event.key !== 'Enter' || event.shiftKey) {
    return
  }

  event.preventDefault()
  await handlePrimaryAction()
}
</script>

<template>
  <footer class="bottom-action-bar" data-testid="bottom-action-bar">
    <div class="composer-card">
      <textarea
        v-model="userPrompt"
        class="composer-input"
        rows="2"
        placeholder="给 DeepSeek 发送消息"
        :disabled="isRequestInFlight"
        @keydown="handleComposerKeydown"
      />

      <div class="composer-toolbar">
        <div class="left-tools">
          <button class="tag-button" :class="{ 'tag-button-active': thinkingEnabled }" type="button" @click="thinkingEnabled = !thinkingEnabled">
            深度思考
          </button>
          <button class="tag-button" :class="{ 'tag-button-active': searchEnabled }" type="button" @click="searchEnabled = !searchEnabled">
            智能搜索
          </button>
        </div>

        <div class="right-tools">
          <button class="clip-button" type="button" aria-label="添加附件">⌕</button>
          <button
            class="send-button primary-button"
            type="button"
            :disabled="isPrimaryActionDisabled"
            aria-label="发送消息"
            @click="handlePrimaryAction"
          >
            ↑
          </button>
        </div>
      </div>
    </div>
  </footer>
</template>

<style scoped>
.bottom-action-bar {
  position: sticky;
  bottom: 0;
  padding: 8px 12px 14px;
  background: var(--color-surface-muted);
}

.composer-card {
  width: 100%;
  max-width: 100%;
  padding: 16px 18px 18px;
  border: 1px solid var(--composer-border, #dfd8cf);
  border-radius: 32px;
  background: var(--composer-surface, #ffffff);
}

.composer-input {
  width: 100%;
  min-height: 74px;
  max-height: 110px;
  resize: none;
  border: none;
  background: transparent;
  color: var(--color-text-primary);
  line-height: 1.55;
  font-size: 16px;
}

.composer-input:focus {
  outline: none;
}

.composer-input::placeholder {
  color: var(--color-text-secondary);
}

.composer-input:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.composer-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.left-tools,
.right-tools {
  display: flex;
  align-items: center;
  gap: 10px;
}

.tag-button {
  min-height: 38px;
  padding: 0 16px;
  border: 1px solid var(--feature-pill-border, #b8c8ff);
  border-radius: 999px;
  background: #ffffff;
  color: #98a1b3;
  cursor: pointer;
  transition: background 120ms ease, color 120ms ease, border-color 120ms ease;
}

.tag-button-active {
  background: var(--feature-pill-bg, #edf2ff);
  color: var(--feature-pill-text, #4d6dff);
}

.clip-button {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--color-text-primary);
  font-size: 26px;
  transform: rotate(45deg);
  cursor: pointer;
}

.send-button {
  width: 50px;
  height: 50px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 50%;
  background: var(--color-accent);
  color: #ffffff;
  font-size: 26px;
  font-weight: 600;
  cursor: pointer;
}

.send-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
