import { createRouter, createWebHistory } from 'vue-router'

import { clearAuthToken, getAuthToken } from '@/auth'
import { getAuthStatus } from '@/api/aiterm'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/chat' },
    { path: '/login', component: () => import('@/views/login') },
    { path: '/chat', component: () => import('@/views/chat') },
    { path: '/history', component: () => import('@/views/history') },
    { path: '/terminal', component: () => import('@/views/terminal') },
    { path: '/nodes', component: () => import('@/views/nodes'), meta: { adminOnly: true } },
    { path: '/users', component: () => import('@/views/users'), meta: { adminOnly: true } },
    { path: '/models', component: () => import('@/views/models'), meta: { adminOnly: true } },
    { path: '/global-settings', component: () => import('@/views/global-settings'), meta: { adminOnly: true } },
    { path: '/tools', component: () => import('@/views/tools/index.vue'), meta: { adminOnly: true } },
  ],
})

router.beforeEach(async (to) => {
  const token = getAuthToken()
  const status = await getAuthStatus().catch(() => null)
  if (!status) {
    clearAuthToken()
    if (to.path === '/login') {
      return true
    }
    return '/login'
  }

  if (status.authenticated && token) {
    if (to.meta.adminOnly && status.user?.role !== 'admin') {
      return '/chat'
    }

    if (to.path === '/login') {
      return '/chat'
    }
    return true
  }

  clearAuthToken()
  if (to.path === '/login') {
    return true
  }

  return '/login'
})

export default router
