<script setup lang="ts">
import type { UserItem } from '@/types/api'
import { formatDateTime } from '@/utils/datetime'

defineProps<{
  items: UserItem[]
  loading: boolean
}>()

const emit = defineEmits<{
  edit: [user: UserItem]
  delete: [user: UserItem]
  'reset-password': [user: UserItem]
}>()

function getRoleLabel(role: string) {
  return role === 'admin' ? '管理员' : '普通用户'
}

function getStatusLabel(status: string) {
  return status === 'active' ? '启用' : '禁用'
}

function getStatusClass(status: string) {
  return status === 'active' ? 'data-table__tag--success' : 'data-table__tag--danger'
}
</script>

<template>
  <div class="data-table">
    <el-table :data="items" :loading="loading" empty-text="暂无用户">
      <el-table-column prop="username" label="用户名" min-width="140" />
      <el-table-column prop="display_name" label="显示名称" min-width="140" />
      <el-table-column label="角色" width="100">
        <template #default="{ row }">
          <span class="data-table__tag" :class="row.role === 'admin' ? 'data-table__tag--info' : ''">
            {{ getRoleLabel(row.role) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <span class="data-table__tag" :class="getStatusClass(row.status)">
            {{ getStatusLabel(row.status) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="最后登录" min-width="140">
        <template #default="{ row }">
          {{ formatDateTime(row.last_login_at) }}
        </template>
      </el-table-column>
      <el-table-column label="创建时间" min-width="140">
        <template #default="{ row }">
          {{ formatDateTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <div class="data-table__actions">
            <el-button link type="primary" @click="emit('edit', row)">编辑</el-button>
            <el-button link @click="emit('reset-password', row)">重置密码</el-button>
            <el-button link type="danger" @click="emit('delete', row)">删除</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
