<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { clearAuthToken } from '@/auth'
import { changeMyPassword, getAuthStatus } from '@/api/aiterm'
import type { UserItem } from '@/types/api'

import AppTopBar from './AppTopBar.vue'
import AppSidebar from './AppSidebar.vue'
import AppTagsView from './AppTagsView.vue'

const route = useRoute()
const router = useRouter()

const showShell = computed(() => route.path !== '/login' && !route.path.match(/^\/share\/[^/]+$/))
const authEnabled = ref(false)
const currentUser = ref<UserItem | null>(null)
const passwordDialogVisible = ref(false)
const passwordSaving = ref(false)
const passwordErrorMessage = ref('')
const passwordForm = ref({
  current_password: '',
  new_password: '',
  confirm_password: '',
})

const openTabs = ref<{ path: string; label: string }[]>([])

const menuLabelMap: Record<string, string> = {
  '/chat': '对话',
  '/agents/workbench': '智能体工作台',
  '/history': '历史',
  '/terminal': '终端',
  '/shares': '分享管理',
  '/workspace/files': '文件浏览',
  '/workspace/agents': '智能体管理',
  '/workspace/skills': '技能',
  '/workspace/scheduler': '定时任务',
  '/workspace/models': '模型配置',
  '/tools/library': '工具库',
  '/tools/my': '我的工具',
  '/profile': '个人中心',
  '/system/users': '用户管理',
  '/system/teams': '团队管理',
  '/system/nodes': '节点管理',
  '/system/sandbox': '沙盒配置',
  '/system/settings': '全局配置',
}

const breadcrumb = computed(() => {
  const path = route.path
  if (path === '/chat') return 'AI 对话 / 对话'
  for (const [p, label] of Object.entries(menuLabelMap)) {
    if (path === p || path.startsWith(p + '/')) return label
  }
  return null
})

const isAdmin = computed(() => !authEnabled.value || currentUser.value?.role === 'admin')

function resolveLabel(path: string): string {
  return menuLabelMap[path] || path
}

function addTab(path: string) {
  if (path === '/login' || path.startsWith('/share/')) return
  const base = path.split('?')[0]
  const exists = openTabs.value.find(t => t.path === base)
  if (!exists) {
    openTabs.value.push({ path: base, label: resolveLabel(base) })
  }
}

function closeTab(path: string) {
  const idx = openTabs.value.findIndex(t => t.path === path)
  if (idx === -1 || path === '/chat') return
  openTabs.value.splice(idx, 1)
  if (route.path === path) {
    const next = openTabs.value[Math.min(idx, openTabs.value.length - 1)]
    if (next) router.push(next.path)
  }
}

function closeOthers(path: string) {
  openTabs.value = openTabs.value.filter(t => t.path === path || t.path === '/chat')
}

function closeAll() {
  openTabs.value = openTabs.value.filter(t => t.path === '/chat')
  router.push('/chat')
}

function closeLeft(path: string) {
  const idx = openTabs.value.findIndex(t => t.path === path)
  openTabs.value = [
    ...openTabs.value.filter(t => t.path === '/chat'),
    ...openTabs.value.slice(idx),
  ]
}

function closeRight(path: string) {
  const idx = openTabs.value.findIndex(t => t.path === path)
  openTabs.value = openTabs.value.slice(0, idx + 1)
}

async function loadAuthStatus() {
  try {
    const status = await getAuthStatus()
    authEnabled.value = status.enabled
    currentUser.value = status.user ?? null
  } catch {
    authEnabled.value = false
    currentUser.value = null
  }
}

watch(() => route.fullPath, () => {
  addTab(route.path)
  loadAuthStatus()
}, { immediate: true })

function openPasswordDialog() {
  passwordForm.value = { current_password: '', new_password: '', confirm_password: '' }
  passwordErrorMessage.value = ''
  passwordDialogVisible.value = true
}

async function submitPasswordChange() {
  if (passwordSaving.value) return
  if (!passwordForm.value.current_password || !passwordForm.value.new_password) {
    passwordErrorMessage.value = '请完整填写当前密码和新密码。'
    return
  }
  if (passwordForm.value.new_password.length < 8) {
    passwordErrorMessage.value = '新密码至少需要 8 位。'
    return
  }
  if (passwordForm.value.new_password !== passwordForm.value.confirm_password) {
    passwordErrorMessage.value = '两次输入的新密码不一致。'
    return
  }
  passwordSaving.value = true
  try {
    await changeMyPassword({
      current_password: passwordForm.value.current_password,
      new_password: passwordForm.value.new_password,
    })
    ElMessage.success('密码修改成功，请重新登录。')
    passwordDialogVisible.value = false
    clearAuthToken()
    router.replace('/login')
  } catch {
    passwordErrorMessage.value = '修改密码失败，请检查当前密码是否正确。'
  } finally {
    passwordSaving.value = false
  }
}
</script>

<template>
  <slot v-if="!showShell" />
  <div v-else class="shell-v2">
    <AppSidebar :is-admin="isAdmin" />
    <div class="shell-v2__right">
      <AppTopBar :current-user="currentUser" :breadcrumb="breadcrumb" @open-password-dialog="openPasswordDialog" />
      <AppTagsView :tabs="openTabs" @close="closeTab" @close-others="closeOthers" @close-all="closeAll"
        @close-left="closeLeft" @close-right="closeRight" />
      <main class="shell-v2__main">
        <router-view />
      </main>
    </div>

    <el-dialog v-model="passwordDialogVisible" title="修改密码" width="420px">
      <el-alert v-if="passwordErrorMessage" :title="passwordErrorMessage" type="warning" show-icon :closable="false" />
      <el-form label-position="top">
        <el-form-item label="当前密码">
          <el-input v-model="passwordForm.current_password" type="password" show-password :disabled="passwordSaving" />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="passwordForm.new_password" type="password" show-password :disabled="passwordSaving" />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input v-model="passwordForm.confirm_password" type="password" show-password :disabled="passwordSaving" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="passwordSaving" @click="passwordDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="passwordSaving" @click="submitPasswordChange">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.shell-v2 {
  display: flex;
  min-height: 100vh;
  background: linear-gradient(180deg, var(--color-bg-secondary) 0%, var(--color-bg-tertiary) 100%);
}

.shell-v2__right {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
}

.shell-v2__main {
  flex: 1;
  overflow-y: auto;
  padding: 0;
}
</style>
