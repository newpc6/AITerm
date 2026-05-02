<script setup lang="ts">
import type { ChatItem } from '@/types/api'
import { formatDateTime } from '@/utils/datetime'

defineProps<{
  deletingChatId: string
  items: ChatItem[]
  loading: boolean
}>()

const emit = defineEmits<{
  delete: [chatId: string]
  open: [chatId: string]
}>()

function getStatusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: '待处理',
    analyzing: '分析中',
    executing: '执行中',
    waiting_confirm: '等待确认',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
  }
  return labels[status] || status
}

function getStatusClass(status: string) {
  const classes: Record<string, string> = {
    pending: 'data-table__tag--warning',
    analyzing: 'data-table__tag--info',
    executing: 'data-table__tag--info',
    waiting_confirm: 'data-table__tag--warning',
    completed: 'data-table__tag--success',
    failed: 'data-table__tag--danger',
    cancelled: 'data-table__tag--danger',
  }
  return classes[status] || ''
}
</script>

<template>
  <div class="data-table">
    <el-table :data="items" :loading="loading" empty-text="暂无历史会话">
      <el-table-column prop="title" label="会话标题" min-width="180" />
      <el-table-column prop="summary" label="摘要" min-width="200" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <span v-if="row.status" class="data-table__tag" :class="getStatusClass(row.status)">
            {{ getStatusLabel(row.status) }}
          </span>
          <span v-else class="data-table__tag">-</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" min-width="140">
        <template #default="{ row }">
          {{ formatDateTime(row.updated_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <div class="data-table__actions">
            <el-button link type="primary" @click="emit('open', row.id)">打开</el-button>
            <el-button link type="danger" :loading="deletingChatId === row.id" @click="emit('delete', row.id)">
              删除
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
