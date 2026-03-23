import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './style.css'

// 引入主题 store 以初始化主题
import { useThemeStore } from './stores/themeStore'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)

// 初始化主题
const themeStore = useThemeStore()
themeStore.setTheme(themeStore.currentThemeId)

app.mount('#app')
