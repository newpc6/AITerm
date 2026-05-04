<script setup lang="ts">
import { SuccessFilled } from '@element-plus/icons-vue'

defineProps<{
  title?: string
  body?: string
}>()
</script>

<template>
  <div class="approved-card">
    <div class="approved-card__header">
      <div class="approved-card__title">
        <el-icon class="approved-card__icon">
          <SuccessFilled />
        </el-icon>
        {{ title || '已批准' }}
      </div>
    </div>
    <pre v-if="body" class="approved-card__code"><code>{{ body }}</code></pre>
  </div>
</template>

<style scoped>
.approved-card {
  display: grid;
  gap: 10px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid var(--color-success-border);
  background: var(--color-success-bg);
}

.approved-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.approved-card__title {
  font-size: var(--font-size-sm);
  font-weight: 700;
  letter-spacing: 0.06em;
  color: rgba(191, 219, 254, 0.88);
  text-transform: uppercase;
  display: flex;
  align-items: center;
}

.approved-card__icon {
  color: var(--color-success);
  margin-right: 6px;
  vertical-align: middle;
}

.approved-card__code {
  margin: var(--spacing-md) 0 0;
  padding: var(--spacing-md) 14px;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid var(--color-border-primary);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-family: Consolas, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
}
</style>
