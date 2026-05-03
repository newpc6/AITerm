<script setup lang="ts">
import { Edit, Delete } from '@element-plus/icons-vue'
import type { Tool } from '@/types/tool'

defineProps<{
  tools: Tool[]
  loading: boolean
}>()

const emit = defineEmits<{
  edit: [tool: Tool]
  delete: [tool: Tool]
  toggleEnabled: [tool: Tool]
}>()
</script>

<template>
  <div class="data-table">
    <el-table :data="tools" v-loading="loading">
      <el-table-column prop="name" label="工具名称" width="180">
        <template #default="{ row }">
          <span class="mono">{{ row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="display_name" label="显示名称" width="180">
        <template #default="{ row }">
          {{ row.display_name || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" min-width="200">
        <template #default="{ row }">
          {{ row.description || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="enabled" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
            {{ row.enabled ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="sandbox_only" label="沙盒限制" width="100">
        <template #default="{ row }">
          <el-tag :type="row.sandbox_only ? 'warning' : 'info'" size="small">
            {{ row.sandbox_only ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link :icon="Edit" @click="emit('edit', row)">编辑</el-button>
          <el-button type="primary" link @click="emit('toggleEnabled', row)">
            {{ row.enabled ? '禁用' : '启用' }}
          </el-button>
          <el-button type="danger" link :icon="Delete" @click="emit('delete', row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.data-table {
  width: 100%;
}

.mono {
  font-family: 'Consolas', 'Monaco', monospace;
  color: var(--color-accent-primary);
}
</style>
