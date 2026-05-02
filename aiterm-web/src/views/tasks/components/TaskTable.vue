<script setup lang="ts">
import type { ExecuteItem } from '@/types/api'
import { formatDateTime } from '@/utils/datetime'

defineProps<{
  tasks: ExecuteItem[]
  loading: boolean
  deletingTaskId: string
}>()

const emit = defineEmits<{
  delete: [taskId: string]
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
    <el-table :data="tasks" :loading="loading" empty-text="暂无任务">
      <el-table-column prop="title" label="标题" min-width="180" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <span class="data-table__tag" :class="getStatusClass(row.status)">
            {{ getStatusLabel(row.status) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="进度" width="120">
        <template #default="{ row }">
          <el-progress :percentage="row.progress" :stroke-width="6" :show-text="true" />
        </template>
      </el-table-column>
      <el-table-column label="创建时间" min-width="140">
        <template #default="{ row }">
          {{ formatDateTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <div class="data-table__actions">
            <el-button link type="danger" :loading="deletingTaskId === row.id" @click="emit('delete', row.id)">
              删除
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
