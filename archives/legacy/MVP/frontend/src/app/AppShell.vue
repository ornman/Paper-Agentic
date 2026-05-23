<script setup lang="ts">
import { getActivePinia } from 'pinia'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import TopNavBar from '../components/layout/TopNavBar.vue'
import BottomActionBar from '../components/layout/BottomActionBar.vue'
import EmptyState from '../components/conversation/EmptyState.vue'
import MessageList from '../components/conversation/MessageList.vue'
import ContextPreview from '../components/conversation/ContextPreview.vue'
import HistoryDrawer from '../components/overlays/HistoryDrawer.vue'
import { createWpsHostAdapter } from '../services/wps-host'
import { createSelectionWatcher } from '../services/wps-selection'
import { useConversationStore } from '../stores/conversation'
import { useHostStore } from '../stores/host'

const activePinia = getActivePinia()
const hostStore = activePinia ? useHostStore(activePinia) : null
const conversationStore = activePinia ? useConversationStore(activePinia) : null
const hostAdapter = hostStore ? createWpsHostAdapter() : null
const selectionWatcher = createSelectionWatcher()

const hasConversationMessages = computed(() => (conversationStore?.messages.length ?? 0) > 0)
const conversationMessages = computed(() => conversationStore?.messages ?? [])
const conversationErrorMessage = computed(() => conversationStore?.errorMessage ?? null)
const currentChatTitle = computed(() => '对话')
const historyDrawerOpen = ref(false)
const showContextPreview = ref(true)
const fontScale = ref<'small' | 'default' | 'large'>('default')
const surfaceTheme = ref<'frost' | 'paper' | 'mist' | 'clay'>('frost')

watch(
  surfaceTheme,
  (nextTheme) => {
    if (typeof window === 'undefined') {
      return
    }

    window.localStorage.setItem('wps-sidebar-theme', nextTheme)
  },
  { immediate: true },
)

const shellStyle = computed<Record<string, string>>(() => {
  const themeMap = {
    frost: {
      topBg: '#f7f4ee',
      bottomBg: '#f7f4ee',
      composerSurface: '#ffffff',
      composerBorder: '#dfd8cf',
      accent: '#aebeff',
      accentSoft: '#edf2ff',
      pillBg: '#edf2ff',
      pillBorder: '#b8c8ff',
      pillText: '#4d6dff',
    },
    paper: {
      topBg: '#faf8f2',
      bottomBg: '#f3efe7',
      composerSurface: '#fffdfa',
      composerBorder: '#ddd3c5',
      accent: '#c5784f',
      accentSoft: '#f3e5da',
      pillBg: 'rgba(235, 241, 250, 0.88)',
      pillBorder: 'rgba(197, 210, 233, 0.94)',
      pillText: '#6579b5',
    },
    mist: {
      topBg: '#f9f9f9',
      bottomBg: '#efefec',
      composerSurface: '#ffffff',
      composerBorder: '#d8d8d2',
      accent: '#b47e67',
      accentSoft: '#efe2db',
      pillBg: 'rgba(236, 239, 243, 0.92)',
      pillBorder: 'rgba(201, 206, 214, 0.96)',
      pillText: '#69717d',
    },
    clay: {
      topBg: '#f9f7f4',
      bottomBg: '#efe3d8',
      composerSurface: '#fffdf9',
      composerBorder: '#d8c6b4',
      accent: '#d17d52',
      accentSoft: '#f3e3d8',
      pillBg: 'rgba(240, 232, 224, 0.9)',
      pillBorder: 'rgba(220, 201, 186, 0.96)',
      pillText: '#8b6b59',
    },
  } as const

  const fontScaleMap = {
    small: {
      body: '13px',
      title: '17px',
      caption: '11px',
    },
    default: {
      body: '14px',
      title: '18px',
      caption: '12px',
    },
    large: {
      body: '15px',
      title: '19px',
      caption: '13px',
    },
  } as const

  const theme = themeMap[surfaceTheme.value]
  const scale = fontScaleMap[fontScale.value]

  return {
    '--shell-top-bg': theme.topBg,
    '--shell-bottom-bg': theme.bottomBg,
    '--composer-surface': theme.composerSurface,
    '--composer-border': theme.composerBorder,
    '--color-accent': theme.accent,
    '--color-accent-soft': theme.accentSoft,
    '--feature-pill-bg': theme.pillBg,
    '--feature-pill-border': theme.pillBorder,
    '--feature-pill-text': theme.pillText,
    '--font-size-body': scale.body,
    '--font-size-title': scale.title,
    '--font-size-caption': scale.caption,
  }
})

function handleOpenHistory() {
  historyDrawerOpen.value = true
}

function handleCloseHistory() {
  historyDrawerOpen.value = false
}

function handleNewChat() {
  conversationStore?.reset()
  historyDrawerOpen.value = false
}

function handleUpdateFontScale(nextScale: 'small' | 'default' | 'large') {
  fontScale.value = nextScale
}

function handleUpdateSurfaceTheme(nextTheme: 'frost' | 'paper' | 'mist' | 'clay') {
  surfaceTheme.value = nextTheme
}

onMounted(async () => {
  if (typeof window !== 'undefined') {
    const persistedTheme = window.localStorage.getItem('wps-sidebar-theme')
    if (persistedTheme === 'frost' || persistedTheme === 'paper' || persistedTheme === 'mist' || persistedTheme === 'clay') {
      surfaceTheme.value = persistedTheme
    }

    showContextPreview.value = window.localStorage.getItem('wps-debug-context') !== '0'
  }

  if (!hostAdapter || !hostStore) {
    return
  }

  await hostAdapter.startPolling(hostStore)

  selectionWatcher.start((snapshot) => {
    conversationStore?.setSelectionContext(snapshot.text)
  })
})

onBeforeUnmount(() => {
  hostAdapter?.stopPolling()
  selectionWatcher.stop()
})
</script>

<template>
  <div class="app-shell" data-testid="app-shell" :style="shellStyle">
    <aside
      class="sidebar-container"
      data-testid="sidebar-container"
      data-sidebar-width="380"
      aria-label="WPS 论文创作辅助侧边栏"
    >
      <div class="top-gradient-bar" aria-hidden="true" />
      <div class="resize-hotspot" aria-hidden="true" title="拖动这里可更容易触发侧边栏调整" />
      <div v-if="!historyDrawerOpen" class="sidebar-chrome" data-testid="sidebar-chrome">
        <TopNavBar
          :title="currentChatTitle"
          @open-history="handleOpenHistory"
          @new-chat="handleNewChat"
        />
      </div>

      <main class="sidebar-main" data-testid="sidebar-main">
        <HistoryDrawer
          v-if="historyDrawerOpen"
          :open="historyDrawerOpen"
          @close="handleCloseHistory"
          @new-chat="handleNewChat"
          @select-session="handleCloseHistory"
          @update-font-scale="handleUpdateFontScale"
          @update-surface-theme="handleUpdateSurfaceTheme"
        />
        <div v-else class="sidebar-content" data-testid="content-area">
          <div v-if="conversationErrorMessage" class="conversation-error" data-testid="conversation-error" role="alert">
            {{ conversationErrorMessage }}
          </div>

          <ContextPreview
            v-if="conversationStore && showContextPreview"
            :written-content="hostStore?.text ?? ''"
            :selected-text="conversationStore.selectionContext"
            :prompt-text="conversationStore.promptContext"
          />

          <MessageList v-if="hasConversationMessages" :messages="conversationMessages" />
          <EmptyState v-else />
        </div>
      </main>

      <BottomActionBar v-if="!historyDrawerOpen" />
    </aside>
  </div>
</template>

<style scoped>
.app-shell {
  width: 100%;
  height: 100%;
  min-height: 100vh;
  background: #ffffff;
  color: var(--color-text-primary);
}

.sidebar-container {
  --sidebar-width: 380px;

  position: relative;
  display: grid;
  grid-template-rows: auto 1fr auto;
  width: 100%;
  max-width: 100%;
  min-height: 100vh;
  margin-left: 0;
  padding: 12px;
  background: #ffffff;
  color: var(--color-text-primary);
  overflow: hidden;
}

.top-gradient-bar {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 80px;
  background: linear-gradient(to bottom, #fafafa 0%, #f5f5f5 50%, #fafafa 100%);
  pointer-events: none;
  z-index: 0;
}

.resize-hotspot {
  position: absolute;
  top: 0;
  right: -6px;
  width: 12px;
  height: 100%;
  cursor: col-resize;
  z-index: 20;
}

.resize-hotspot::before {
  content: '';
  position: absolute;
  top: 0;
  left: 5px;
  width: 2px;
  height: 100%;
  background: linear-gradient(180deg, rgba(201, 106, 68, 0) 0%, rgba(201, 106, 68, 0.18) 20%, rgba(201, 106, 68, 0.18) 80%, rgba(201, 106, 68, 0) 100%);
  opacity: 0;
  transition: opacity 120ms ease;
}

.resize-hotspot:hover::before {
  opacity: 1;
}

.sidebar-chrome {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 10px;
  padding: 4px 4px 8px;
  background: transparent;
}

.sidebar-main {
  position: relative;
  z-index: 1;
  min-height: 0;
  padding-top: 8px;
}

.sidebar-content {
  height: 100%;
  display: grid;
  align-content: start;
  gap: 18px;
  padding: 0 4px 4px;
  overflow-y: auto;
  overflow-x: hidden;
}

.conversation-error {
  margin-bottom: var(--space-3);
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(180, 35, 24, 0.35);
  background: rgba(180, 35, 24, 0.08);
  color: #b42318;
  font-size: var(--font-size-caption);
  line-height: 1.6;
}
</style>
