<template>
  <div class="empty-state">
    <div class="empty-icon">
      <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
        <circle cx="32" cy="32" r="30" stroke="#e5e5e5" stroke-width="2"/>
        <path d="M22 32h20M32 22v20" stroke="#b3b3b3" stroke-width="2" stroke-linecap="round"/>
      </svg>
    </div>
    <h2 class="empty-title">论文写作助手</h2>
    <p class="empty-description">基于 RAG 的学术问答系统</p>
    <div class="empty-tips">
      <div class="tip-item">💡 支持流式输出</div>
      <div class="tip-item">📚 引用论文来源</div>
      <div class="tip_item">🔍 智能检索答案</div>
    </div>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--claude-spacing-xl) var(--claude-spacing-lg);
  text-align: center;
}

.empty-icon {
  margin-bottom: var(--claude-spacing-md);
  opacity: 0.5;
}

.empty-title {
  margin: 0 0 var(--claude-spacing-sm);
  font-size: 18px;
  font-weight: 600;
  color: var(--claude-text-primary);
}

.empty-description {
  margin: 0 0 var(--claude-spacing-lg);
  font-size: 14px;
  color: var(--claude-text-muted);
}

.empty-tips {
  display: flex;
  flex-direction: column;
  gap: var(--claude-spacing-sm);
}

.tip-item {
  font-size: 13px;
  color: var(--claude-text-secondary);
  padding: var(--claude-spacing-xs) var(--claude-spacing-md);
  background: var(--claude-bg-muted);
  border-radius: var(--claude-radius-full);
}
</style>
