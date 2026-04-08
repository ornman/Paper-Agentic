<script setup lang="ts">
import { computed, ref } from 'vue'

interface HistoryDrawerProps {
  open?: boolean
}

type DrawerSection = 'nav' | 'chats' | 'knowledge' | 'account' | 'settings'
type FontScale = 'small' | 'default' | 'large'
type SurfaceTheme = 'frost' | 'paper' | 'mist' | 'clay'

interface SessionSummary {
  id: string
  title: string
  preview: string
  updatedAt: string
}

const props = withDefaults(defineProps<HistoryDrawerProps>(), {
  open: false,
})

const emit = defineEmits<{
  (event: 'close'): void
  (event: 'select-session', id: string): void
  (event: 'new-chat'): void
  (event: 'update-font-scale', value: FontScale): void
  (event: 'update-surface-theme', value: SurfaceTheme): void
}>()

const currentSection = ref<DrawerSection>('nav')
const selectedFontScale = ref<FontScale>('default')
const selectedSurfaceTheme = ref<SurfaceTheme>('paper')
const sessions = ref<SessionSummary[]>([])

const filteredSessions = computed(() => [...sessions.value].sort((left, right) => right.updatedAt.localeCompare(left.updatedAt)))

function openSection(section: DrawerSection) {
  currentSection.value = section
}

function handleSelectFontScale(value: FontScale) {
  selectedFontScale.value = value
  emit('update-font-scale', value)
}

function handleSelectSurfaceTheme(value: SurfaceTheme) {
  selectedSurfaceTheme.value = value
  emit('update-surface-theme', value)
}

function formatUpdatedAt(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}
</script>

<template>
  <section v-if="props.open" class="history-page" data-testid="history-drawer-shell" aria-label="历史记录页面">
    <section v-if="currentSection === 'nav'" class="nav-page">
      <h1 class="brand-title">论文助手</h1>

      <nav class="nav-menu">
        <button class="nav-link nav-link-accent" type="button" @click="emit('new-chat')">
          <span class="nav-bubble nav-bubble-accent"><span class="nav-bubble-plus">＋</span></span>
          <span class="nav-text">新聊天</span>
        </button>

        <button class="nav-link" type="button" @click="openSection('chats')">
          <span class="nav-bubble nav-bubble-line" />
          <span class="nav-text">聊天记录</span>
        </button>

        <button class="nav-link" type="button" @click="openSection('knowledge')">
          <span class="nav-folder" />
          <span class="nav-text">知识库</span>
        </button>

        <button class="nav-link" type="button" @click="openSection('settings')">
          <span class="nav-artifact">
            <span class="artifact-dot" />
            <span class="artifact-square" />
          </span>
          <span class="nav-text">拓展</span>
        </button>
      </nav>

      <footer class="nav-footer">
        <button class="account-button" type="button" @click="openSection('account')">
          <span class="account-avatar">Y</span>
          <span class="account-name">Yue</span>
        </button>

        <button class="settings-button" type="button" aria-label="打开设置" @click="openSection('settings')">
          ⚙
        </button>
      </footer>
    </section>

    <section v-else-if="currentSection === 'chats'" class="subpage">
      <header class="subpage-topbar">
        <button class="subpage-icon" type="button" aria-label="返回导航" @click="openSection('nav')">
          ☰
        </button>
      </header>

      <h1 class="subpage-title">聊天记录</h1>

      <div class="search-shell">
        <span class="search-icon">⌕</span>
        <input class="search-input" type="text" placeholder="搜索聊天记录" />
      </div>

      <div class="subpage-content">
        <p v-if="filteredSessions.length === 0" class="empty-copy">这里暂时还没有聊天记录。</p>
        <button
          v-for="session in filteredSessions"
          :key="session.id"
          class="history-item"
          type="button"
          @click="emit('select-session', session.id)"
        >
          <div class="history-item-topline">
            <span class="history-item-title">{{ session.title }}</span>
            <time class="history-item-time">{{ formatUpdatedAt(session.updatedAt) }}</time>
          </div>
          <span class="history-item-preview">{{ session.preview }}</span>
        </button>
      </div>

      <button class="floating-new-chat" type="button" @click="emit('new-chat')">
        <span class="floating-icon">＋</span>
        <span>New chat</span>
      </button>
    </section>

    <section v-else-if="currentSection === 'knowledge'" class="subpage">
      <header class="subpage-topbar subpage-topbar-spread">
        <button class="subpage-icon" type="button" aria-label="返回导航" @click="openSection('nav')">
          ☰
        </button>
        <button class="subpage-icon" type="button" aria-label="新建知识库项目">＋</button>
      </header>

      <h1 class="subpage-title">知识库</h1>

      <div class="search-shell">
        <span class="search-icon">⌕</span>
        <input class="search-input" type="text" placeholder="搜索知识库" />
      </div>

      <div class="subpage-content">
        <p class="empty-copy">这里暂时还没有知识库项目。</p>
      </div>
    </section>

    <section v-else-if="currentSection === 'account'" class="subpage simple-panel">
      <button class="subpage-icon subpage-back" type="button" aria-label="返回导航" @click="openSection('nav')">
        ←
      </button>
      <h1 class="subpage-title">账户</h1>
      <p class="empty-copy">这里预留给个人信息页面。</p>
    </section>

    <section v-else class="subpage simple-panel">
      <button class="subpage-icon subpage-back" type="button" aria-label="返回导航" @click="openSection('nav')">
        ←
      </button>
      <h1 class="subpage-title">设置</h1>

      <div class="settings-group">
        <p class="settings-label">字体大小</p>
        <div class="chip-row">
          <button class="chip-button" :class="{ 'chip-button-active': selectedFontScale === 'small' }" type="button" @click="handleSelectFontScale('small')">小</button>
          <button class="chip-button" :class="{ 'chip-button-active': selectedFontScale === 'default' }" type="button" @click="handleSelectFontScale('default')">默认</button>
          <button class="chip-button" :class="{ 'chip-button-active': selectedFontScale === 'large' }" type="button" @click="handleSelectFontScale('large')">大</button>
        </div>
      </div>

      <div class="settings-group">
        <p class="settings-label">页面风格</p>
        <div class="chip-row chip-row-stacked">
          <button class="chip-button" :class="{ 'chip-button-active': selectedSurfaceTheme === 'frost' }" type="button" @click="handleSelectSurfaceTheme('frost')">冷白霜面</button>
          <button class="chip-button" :class="{ 'chip-button-active': selectedSurfaceTheme === 'paper' }" type="button" @click="handleSelectSurfaceTheme('paper')">纸张米白</button>
          <button class="chip-button" :class="{ 'chip-button-active': selectedSurfaceTheme === 'mist' }" type="button" @click="handleSelectSurfaceTheme('mist')">雾灰轻白</button>
          <button class="chip-button" :class="{ 'chip-button-active': selectedSurfaceTheme === 'clay' }" type="button" @click="handleSelectSurfaceTheme('clay')">暖泥柔橙</button>
        </div>
      </div>
    </section>
  </section>
</template>

<style scoped>
.history-page {
  position: absolute;
  inset: 0;
  background: var(--color-surface-muted);
  z-index: 5;
}

.nav-page,
.subpage {
  min-height: 100%;
  display: grid;
  align-content: start;
  padding: 28px 28px 24px;
  background: var(--color-surface-muted);
}

.nav-page {
  grid-template-rows: auto auto 1fr auto;
}

.brand-title,
.subpage-title {
  color: var(--color-text-primary);
  font-family: var(--font-family-display);
  font-size: 42px;
  line-height: 1;
  font-weight: 700;
}

.brand-title {
  margin-bottom: 46px;
}

.nav-menu {
  display: grid;
  gap: 26px;
}

.nav-link {
  display: inline-flex;
  align-items: center;
  gap: 18px;
  border: none;
  background: transparent;
  color: #41403b;
  text-align: left;
  cursor: pointer;
}

.nav-link-accent {
  color: var(--color-accent);
}

.nav-text {
  font-size: 20px;
  line-height: 1.2;
}

.nav-bubble {
  position: relative;
  width: 24px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
}

.nav-bubble-accent {
  border: 2px solid var(--color-accent);
}

.nav-bubble-accent::after,
.nav-bubble-line::after {
  content: '';
  position: absolute;
  left: 4px;
  bottom: -6px;
  width: 8px;
  height: 8px;
  border-left: inherit;
  border-bottom: inherit;
  border-radius: 0 0 0 6px;
}

.nav-bubble-plus {
  font-size: 14px;
  line-height: 1;
  font-weight: 700;
}

.nav-bubble-line {
  border: 2px solid #47443f;
}

.nav-folder {
  position: relative;
  width: 25px;
  height: 18px;
  border: 2px solid #47443f;
  border-radius: 4px;
}

.nav-folder::before {
  content: '';
  position: absolute;
  top: -6px;
  left: 2px;
  width: 11px;
  height: 6px;
  border: 2px solid #47443f;
  border-bottom: none;
  border-radius: 4px 4px 0 0;
  background: var(--color-surface-muted);
}

.nav-artifact {
  position: relative;
  width: 26px;
  height: 22px;
}

.artifact-dot,
.artifact-square {
  position: absolute;
  border: 2px solid #47443f;
}

.artifact-dot {
  top: 0;
  left: 0;
  width: 10px;
  height: 10px;
  transform: rotate(45deg);
}

.artifact-square {
  right: 0;
  bottom: 0;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.nav-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: auto;
}

.account-button {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  border: none;
  background: transparent;
  color: #302e2a;
  cursor: pointer;
}

.account-avatar {
  width: 44px;
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #383733;
  color: #f5f4f0;
  font-size: 18px;
  font-weight: 600;
}

.account-name {
  font-size: 18px;
}

.settings-button,
.subpage-icon {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-primary);
  font-size: 28px;
  cursor: pointer;
}

.subpage-topbar {
  display: flex;
  justify-content: flex-start;
  margin-bottom: 22px;
}

.subpage-topbar-spread {
  justify-content: space-between;
}

.subpage-title {
  margin-bottom: 24px;
}

.search-shell {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 56px;
  padding: 0 18px;
  border: 1px solid rgba(216, 209, 198, 0.98);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.94);
}

.search-icon {
  color: #7e786f;
  font-size: 22px;
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  color: #2f2d29;
  font-size: 17px;
}

.search-input:focus {
  outline: none;
}

.subpage-content {
  display: grid;
  align-content: start;
  gap: 12px;
  min-height: 400px;
  padding-top: 22px;
}

.empty-copy {
  color: var(--color-text-secondary);
  font-size: 15px;
  line-height: 1.7;
}

.history-item {
  display: grid;
  gap: 8px;
  padding: 16px 18px;
  border: 1px solid rgba(216, 209, 198, 0.88);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.82);
  text-align: left;
  cursor: pointer;
}

.history-item-topline {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.history-item-title {
  color: var(--color-text-primary);
  font-size: 16px;
  font-weight: 600;
}

.history-item-time {
  color: var(--color-text-secondary);
  font-size: 12px;
}

.history-item-preview {
  color: var(--color-text-secondary);
  font-size: 14px;
  line-height: 1.6;
}

.floating-new-chat {
  position: absolute;
  right: 24px;
  bottom: 28px;
  display: inline-flex;
  align-items: center;
  gap: 12px;
  min-height: 64px;
  padding: 0 24px;
  border: none;
  border-radius: 999px;
  background: var(--color-accent);
  color: #fffdfa;
  font-size: 18px;
  font-weight: 700;
  box-shadow: 0 6px 18px rgba(116, 73, 41, 0.18);
  cursor: pointer;
}

.floating-icon {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.18);
  font-size: 20px;
}

.simple-panel {
  gap: 18px;
}

.subpage-back {
  margin-bottom: 8px;
}

.settings-group {
  display: grid;
  gap: 10px;
}

.settings-label {
  color: var(--color-text-primary);
  font-size: 14px;
  font-weight: 600;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.chip-row-stacked {
  display: grid;
}

.chip-button {
  min-height: 38px;
  padding: 0 14px;
  border: 1px solid rgba(216, 209, 198, 0.94);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.88);
  color: #3e3b36;
  cursor: pointer;
}

.chip-button-active {
  border-color: var(--color-accent);
  background: var(--color-accent-soft);
  color: var(--color-accent);
  font-weight: 600;
}
</style>
