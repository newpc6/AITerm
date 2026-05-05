<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { clearAuthToken } from '@/auth'
import { changeMyPassword, getAuthStatus, logout } from '@/api/aiterm'
import type { UserItem } from '@/types/api'

const route = useRoute()
const router = useRouter()

const mainLinks = [
  { to: '/chat', label: '对话' },
  { to: '/history', label: '历史' },
  { to: '/terminal', label: '终端' },
]

const systemManageLinks = [
  { to: '/files', label: '文件管理' },
  { to: '/users', label: '用户管理', adminOnly: true },
  { to: '/shares', label: '分享管理', adminOnly: true },
]

const systemConfigLinks = [
  { to: '/models', label: '模型配置' },
  { to: '/global-settings', label: '全局配置' },
  { to: '/nodes', label: '节点管理' },
  { to: '/tools', label: '工具管理' },
]

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

const isAdmin = computed(() => !authEnabled.value || currentUser.value?.role === 'admin')

const visibleSystemManageLinks = computed(() =>
  systemManageLinks.filter((link) => !link.adminOnly || isAdmin.value)
)

const visibleSystemConfigLinks = computed(() =>
  isAdmin.value ? systemConfigLinks : []
)

const currentUserLabel = computed(() => currentUser.value?.display_name || currentUser.value?.username || '')

const currentSystemManageLink = computed(() => {
  return systemManageLinks.find((link) => route.path === link.to || route.path.startsWith(link.to + '/'))
})

const currentSystemConfigLink = computed(() => {
  return systemConfigLinks.find((link) => route.path === link.to || route.path.startsWith(link.to + '/'))
})

const breadcrumb = computed(() => {
  if (currentSystemManageLink.value) {
    return `系统管理 / ${currentSystemManageLink.value.label}`
  }
  if (currentSystemConfigLink.value) {
    return `系统配置 / ${currentSystemConfigLink.value.label}`
  }
  return null
})

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

watch(
  () => route.fullPath,
  () => {
    void loadAuthStatus()
  },
  { immediate: true },
)

function openPasswordDialog() {
  passwordForm.value = {
    current_password: '',
    new_password: '',
    confirm_password: '',
  }
  passwordErrorMessage.value = ''
  passwordDialogVisible.value = true
}

async function submitPasswordChange() {
  if (passwordSaving.value) {
    return
  }
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
  passwordErrorMessage.value = ''

  try {
    await changeMyPassword({
      current_password: passwordForm.value.current_password,
      new_password: passwordForm.value.new_password,
    })
    ElMessage.success('密码修改成功，请重新登录。')
    passwordDialogVisible.value = false
    currentUser.value = null
    clearAuthToken()
    void router.replace('/login')
  } catch {
    passwordErrorMessage.value = '修改密码失败，请检查当前密码是否正确。'
  } finally {
    passwordSaving.value = false
  }
}

async function handleLogout() {
  try {
    await logout()
  } catch {
    // Ignore logout API failures and clear local token anyway.
  } finally {
    currentUser.value = null
    clearAuthToken()
    void router.replace('/login')
  }
}
</script>

<template>
  <slot v-if="!showShell" />
  <div v-else class="shell">
    <header class="shell__header">
      <div class="shell__brand">AITerm</div>
      <nav class="shell__nav">
        <RouterLink v-for="link in mainLinks" :key="link.to" :to="link.to" class="shell__link"
          :class="{ 'is-active': route.path === link.to }">
          {{ link.label }}
        </RouterLink>
        <el-dropdown trigger="hover" :hide-on-click="false" :class="{ 'is-active': !!currentSystemManageLink }">
          <span class="shell__link shell__link--dropdown">
            系统管理
            <el-icon class="el-icon--right"><svg viewBox="0 0 24 24" fill="currentColor" width="12" height="12">
                <path d="M7 10l5 5 5-5z" />
              </svg></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-for="link in visibleSystemManageLinks" :key="link.to"
                :class="{ 'is-active': route.path === link.to }">
                <RouterLink :to="link.to" class="shell__dropdown-link">{{ link.label }}</RouterLink>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-dropdown v-if="isAdmin" trigger="hover" :hide-on-click="false"
          :class="{ 'is-active': !!currentSystemConfigLink }">
          <span class="shell__link shell__link--dropdown">
            系统配置
            <el-icon class="el-icon--right"><svg viewBox="0 0 24 24" fill="currentColor" width="12" height="12">
                <path d="M7 10l5 5 5-5z" />
              </svg></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-for="link in visibleSystemConfigLinks" :key="link.to"
                :class="{ 'is-active': route.path === link.to }">
                <RouterLink :to="link.to" class="shell__dropdown-link">{{ link.label }}</RouterLink>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </nav>
      <div class="shell__actions">
        <span v-if="breadcrumb" class="shell__breadcrumb">{{ breadcrumb }}</span>
        <span v-if="currentUserLabel" class="shell__user">{{ currentUserLabel }}</span>
        <el-button v-if="currentUserLabel" text @click="openPasswordDialog">修改密码</el-button>
        <el-button text @click="handleLogout">退出</el-button>
      </div>
    </header>
    <main class="shell__content" :class="{ 'shell__content--wide': route.path === '/chat' }">
      <slot />
    </main>

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
.shell__link--dropdown {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
}

.shell__link.is-active {
  color: var(--el-color-primary);
  font-weight: 500;
}

.shell__dropdown-link {
  color: inherit;
  text-decoration: none;
}

.shell__breadcrumb {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  padding: 4px 12px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
}
</style>
