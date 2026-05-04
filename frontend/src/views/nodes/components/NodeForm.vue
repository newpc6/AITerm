<script setup lang="ts">
import type { NodePayload } from '@/types/api'

defineProps<{
  form: NodePayload
  editing: boolean
  loading: boolean
  saving: boolean
}>()

const emit = defineEmits<{
  cancel: []
  save: []
}>()
</script>

<template>
  <el-form label-position="top">
    <el-form-item label="名称">
      <el-input v-model="form.name" placeholder="请输入节点名称" :disabled="loading || saving" />
    </el-form-item>

    <el-form-item label="主机">
      <el-input v-model="form.host" placeholder="请输入主机地址" :disabled="loading || saving" />
    </el-form-item>

    <el-form-item label="端口">
      <el-input-number v-model="form.port" :min="1" :max="65535" :disabled="loading || saving" style="width: 100%" />
    </el-form-item>
  </el-form>

  <div class="dialog-footer">
    <el-button :disabled="loading || saving" @click="emit('cancel')">取消</el-button>
    <el-button type="primary" :loading="saving" @click="emit('save')">
      {{ editing ? '保存修改' : '添加节点' }}
    </el-button>
  </div>
</template>

<style scoped>
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
}
</style>
