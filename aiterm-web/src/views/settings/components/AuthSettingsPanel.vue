<script setup lang="ts">
import type { AuthSettingsData, AuthSettingsPayload } from '@/types/api'

defineProps<{
  form: AuthSettingsPayload
  loading: boolean
  saving: boolean
  settings: AuthSettingsData | null
}>()

const emit = defineEmits<{
  reset: []
  save: []
}>()
</script>

<template>
  <div class="settings-panel">
    <el-form label-position="top">
      <el-form-item label="启用登录保护">
        <el-switch v-model="form.enabled" :disabled="loading || saving" />
      </el-form-item>

      <el-form-item label="允许密码登录">
        <el-switch v-model="form.allow_password_login" :disabled="loading || saving" />
      </el-form-item>

      <el-form-item label="会话时长（小时）">
        <el-input-number v-model="form.session_ttl_hours" :min="1" :max="168" :disabled="loading || saving" />
      </el-form-item>
    </el-form>

    <el-descriptions v-if="settings" :column="1" border>
      <el-descriptions-item label="当前状态">
        {{ settings.enabled ? '已启用登录保护' : '未启用登录保护' }}
      </el-descriptions-item>
    </el-descriptions>

    <div class="settings-panel__actions">
      <el-button :disabled="loading || saving" @click="emit('reset')">重置</el-button>
      <el-button type="primary" :loading="saving" @click="emit('save')">保存</el-button>
    </div>
  </div>
</template>

<style scoped>
.settings-panel {
  display: grid;
  gap: 20px;
}

.settings-panel__actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
