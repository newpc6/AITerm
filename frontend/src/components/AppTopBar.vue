<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { User, Key, SwitchButton } from '@element-plus/icons-vue'

import { clearAuthToken } from '@/auth'
import { logout } from '@/api/aiterm'
import type { UserItem } from '@/types/api'

const props = defineProps<{
  currentUser: UserItem | null
  breadcrumb: string | null
}>()

const emit = defineEmits<{
  openPasswordDialog: []
  userChanged: []
}>()

const route = useRoute()
const router = useRouter()

const userLabel = computed(() => props.currentUser?.display_name || props.currentUser?.username || '')

function goProfile() {
  router.push('/profile')
}

function openPasswordDialog() {
  emit('openPasswordDialog')
}

async function handleLogout() {
  try {
    await logout()
  } catch {
    // ignore
  } finally {
    clearAuthToken()
    router.replace('/login')
  }
}
</script>

<template>
  <div class="topbar">
    <div class="topbar__left">
      <span class="topbar__logo" @click="router.push('/chat')">AITerm</span>
      <span class="topbar__sep">/</span>
      <span v-if="breadcrumb" class="topbar__breadcrumb">{{ breadcrumb }}</span>
    </div>
    <div class="topbar__right">
      <el-dropdown v-if="userLabel" trigger="click" @command="(cmd: string) => { if (cmd === 'profile') goProfile(); else if (cmd === 'password') openPasswordDialog(); else if (cmd === 'logout') handleLogout(); }">
        <span class="topbar__user">
          <el-icon><User /></el-icon>
          <span>{{ userLabel }}</span>
          <el-icon class="topbar__user-arrow"><svg viewBox="0 0 24 24" fill="currentColor" width="14" height="14"><path d="M7 10l5 5 5-5z"/></svg></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">
              <el-icon><User /></el-icon> 个人中心
            </el-dropdown-item>
            <el-dropdown-item command="password">
              <el-icon><Key /></el-icon> 修改密码
            </el-dropdown-item>
            <el-dropdown-item divided command="logout">
              <el-icon><SwitchButton /></el-icon> 退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <span v-else class="topbar__user topbar__user--guest" @click="router.push('/login')">登录</span>
    </div>
  </div>
</template>

<style scoped>
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 48px;
  padding: 0 20px;
  background: var(--color-bg-secondary);
  border-bottom: 1px solid var(--color-border-primary);
  flex-shrink: 0;
}

.topbar__left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.topbar__logo {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-accent-primary);
  cursor: pointer;
  user-select: none;
}

.topbar__sep {
  color: var(--color-text-muted);
  font-size: 14px;
}

.topbar__breadcrumb {
  font-size: 13px;
  color: var(--color-text-secondary);
}

.topbar__right {
  display: flex;
  align-items: center;
}

.topbar__user {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: var(--color-text-secondary);
  font-size: 13px;
  padding: 4px 8px;
  border-radius: 6px;
  transition: background var(--transition-fast);
}

.topbar__user:hover {
  background: var(--color-bg-card);
  color: var(--color-text-primary);
}

.topbar__user--guest {
  color: var(--color-accent-primary);
}

.topbar__user-arrow {
  font-size: 12px;
  color: var(--color-text-muted);
}
</style>
