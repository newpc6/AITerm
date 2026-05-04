<script setup lang="ts">
import type { UserPayload } from '@/types/api'

defineProps<{
  form: UserPayload
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
    <el-form-item label="用户名">
      <el-input v-model="form.username" placeholder="请输入用户名" :disabled="loading || saving || editing" />
    </el-form-item>

    <el-form-item label="显示名称">
      <el-input v-model="form.display_name" placeholder="请输入显示名称" :disabled="loading || saving" />
    </el-form-item>

    <el-form-item v-if="!editing" label="初始密码">
      <el-input v-model="form.password" type="password" show-password placeholder="请输入初始密码（至少8位）"
        :disabled="loading || saving" />
    </el-form-item>

    <el-form-item label="角色">
      <el-select v-model="form.role" :disabled="loading || saving" style="width: 100%">
        <el-option label="管理员" value="admin" />
        <el-option label="普通用户" value="user" />
      </el-select>
    </el-form-item>

    <el-form-item label="状态">
      <el-select v-model="form.status" :disabled="loading || saving" style="width: 100%">
        <el-option label="启用" value="active" />
        <el-option label="禁用" value="disabled" />
      </el-select>
    </el-form-item>
  </el-form>

  <div class="dialog-footer">
    <el-button :disabled="loading || saving" @click="emit('cancel')">取消</el-button>
    <el-button type="primary" :loading="saving" @click="emit('save')">
      {{ editing ? '保存修改' : '创建用户' }}
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
