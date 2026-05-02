<script setup lang="ts">
defineProps<{
  hint?: string
  loading?: boolean
}>()

const emit = defineEmits<{
  confirm: [approved: boolean]
}>()
</script>

<template>
  <div class="approval-card">
    <p class="approval-card__hint">{{ hint || '该操作需要人工确认后才会继续执行。' }}</p>
    <div class="approval-card__actions">
      <el-button type="primary" :loading="loading" @click="emit('confirm', true)">批准执行</el-button>
      <el-button :disabled="loading" @click="emit('confirm', false)">拒绝</el-button>
    </div>
  </div>
</template>

<style scoped>
.approval-card {
  display: grid;
  gap: 10px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border-primary);
}

.approval-card__hint {
  margin: 0;
  color: var(--color-warning);
}

.approval-card__actions {
  display: flex;
  gap: 12px;
}
</style>
