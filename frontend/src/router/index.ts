import { createRouter, createWebHistory } from 'vue-router'

import { clearAuthToken, getAuthToken } from '@/auth'
import { getAuthStatus } from '@/api/aiterm'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/chat' },
    { path: '/login', component: () => import('@/views/login') },
    { path: '/share/:shareId', component: () => import('@/views/share'), meta: { public: true } },
    { path: '/chat', component: () => import('@/views/chat') },
    { path: '/history', component: () => import('@/views/history') },
    { path: '/terminal', component: () => import('@/views/terminal') },
    { path: '/files', component: () => import('@/views/files/index.vue') },
    { path: '/nodes', component: () => import('@/views/nodes'), meta: { adminOnly: true } },
    { path: '/users', component: () => import('@/views/users'), meta: { adminOnly: true } },
    { path: '/shares', component: () => import('@/views/shares/index.vue'), meta: { adminOnly: true } },
    { path: '/models', component: () => import('@/views/models'), meta: { adminOnly: true } },
    { path: '/global-settings', component: () => import('@/views/global-settings'), meta: { adminOnly: true } },
    { path: '/tools', component: () => import('@/views/tools/index.vue'), meta: { adminOnly: true } },
  ],
})

router.beforeEach(async (to) => {
  if (to.meta.public) {
    return true
  }

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
