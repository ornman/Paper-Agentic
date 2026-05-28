import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '../views/ChatView.vue'
import SettingsView from '../views/SettingsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: ChatView },
    { path: '/settings', component: SettingsView },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

export default router
