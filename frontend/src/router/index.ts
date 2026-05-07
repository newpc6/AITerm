import { createRouter, createWebHistory } from 'vue-router'

import { clearAuthToken, getAuthToken } from '@/auth'
import { getAuthStatus } from '@/api/aiterm'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/chat' },
    { path: '/login', component: () => import('@/views/login') },
    { path: '/share/:shareId', component: () => import('@/views/share'), meta: { public: true } },

    // AI 对话
    { path: '/chat', component: () => import('@/views/chat') },
    { path: '/agents/workbench', component: () => import('@/views/agents/workbench') },
    { path: '/history', component: () => import('@/views/history') },
    { path: '/terminal', component: () => import('@/views/terminal') },
    { path: '/shares', component: () => import('@/views/shares/index.vue') },

    // 工作空间
    { path: '/workspace/files', component: () => import('@/views/files/workspace') },
    { path: '/workspace/agents', component: () => import('@/views/agents') },
    { path: '/workspace/skills', component: () => import('@/views/skills') },
    { path: '/workspace/scheduler', component: () => import('@/views/scheduler') },
    { path: '/workspace/models', component: () => import('@/views/models') },

    // 工具
    { path: '/tools/library', component: () => import('@/views/tools/index.vue'), meta: { adminOnly: true } },
    { path: '/tools/my', component: () => import('@/views/tools/my') },

    // 个人
    { path: '/profile', component: () => import('@/views/profile') },

    // 组织管理
    { path: '/system/users', component: () => import('@/views/users'), meta: { adminOnly: true } },
    { path: '/system/teams', component: () => import('@/views/teams'), meta: { adminOnly: true } },

    // 系统管理
    { path: '/system/nodes', component: () => import('@/views/nodes'), meta: { adminOnly: true } },
    { path: '/system/sandbox', component: () => import('@/views/sandbox'), meta: { adminOnly: true } },
    { path: '/system/settings', component: () => import('@/views/global-settings'), meta: { adminOnly: true } },

    // 旧路由重定向
    { path: '/files', redirect: '/workspace/files' },
    { path: '/nodes', redirect: '/system/nodes' },
    { path: '/users', redirect: '/system/users' },
    { path: '/models', redirect: '/workspace/models' },
    { path: '/global-settings', redirect: '/system/settings' },
    { path: '/tools', redirect: '/tools/library' },
    { path: '/sandbox', redirect: '/system/sandbox' },
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
