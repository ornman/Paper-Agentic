import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './styles/tokens.css'
import './style.css'

// Task 1 继续保留 Pinia 根注入。
// 这样后续任务接入状态中心时不需要再改启动入口。
const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.mount('#app')
