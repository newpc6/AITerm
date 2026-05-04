<script setup lang="ts">
import type { NodeItem } from '@/types/api'

defineProps<{
  nodes: NodeItem[]
  loading: boolean
}>()

const emit = defineEmits<{
  edit: [node: NodeItem]
  delete: [node: NodeItem]
}>()

function getStatusLabel(status: string) {
  if (status.startsWith('online')) {
    return '在线'
  }
  return '离线'
}

function getStatusClass(status: string) {
  if (status.startsWith('online')) {
    return 'data-table__tag--success'
  }
  return 'data-table__tag--danger'
}
</script>

<template>
  <div class="data-table">
    <el-table :data="nodes" :loading="loading" empty-text="暂无节点">
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column prop="host" label="主机" min-width="160" />
      <el-table-column prop="port" label="端口" width="80" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <span class="data-table__tag" :class="getStatusClass(row.status)">
            {{ getStatusLabel(row.status) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="id" label="ID" min-width="100" />
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <div class="data-table__actions">
            <el-button link type="primary" @click="emit('edit', row)">编辑</el-button>
            <el-button link type="danger" @click="emit('delete', row)">删除</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
