<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { clearAuthToken } from '@/auth'
import { changeMyPassword, getAuthStatus, logout } from '@/api/aiterm'
import type { UserItem } from '@/types/api'

const route = useRoute()
const router = useRouter()

const links = [
  { to: '/chat', label: '对话' },
  { to: '/history', label: '历史' },
  { to: '/terminal', label: '终端' },
  { to: '/nodes', label: '节点' },
  { to: '/tools', label: '工具', adminOnly: true },
  { to: '/users', label: '用户', adminOnly: true },
  { to: '/models', label: '模型配置', adminOnly: true },
  { to: '/global-settings', label: '全局配置', adminOnly: true },
]

const showShell = computed(() => route.path !== '/login')
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
const visibleLinks = computed(() =>
  links.filter((link) => !link.adminOnly || !authEnabled.value || currentUser.value?.role === 'admin'),
)
const currentUserLabel = computed(() => currentUser.value?.display_name || currentUser.value?.username || '')

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
        <RouterLink v-for="link in visibleLinks" :key="link.to" :to="link.to" class="shell__link">
          {{ link.label }}
        </RouterLink>
      </nav>
      <div class="shell__actions">
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
