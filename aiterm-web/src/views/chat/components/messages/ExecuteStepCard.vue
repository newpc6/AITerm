<script setup lang="ts">
import { Loading, VideoPause } from '@element-plus/icons-vue'
import MarkdownContent from '@/components/MarkdownContent.vue'

defineProps<{
  stepLabel?: string
  title?: string
  command?: string
  body?: string
  isStreaming?: boolean
  canStopExecute?: boolean
}>()

const emit = defineEmits<{
  stopExecute: []
}>()
</script>

<template>
  <div class="execute-card execute-card--step">
    <div class="execute-card__header">
      <div class="execute-card__title">{{ stepLabel || title || '执行中' }}</div>
      <div class="execute-card__actions">
        <el-icon v-if="isStreaming" class="execute-card__loading is-loading">
          <Loading />
        </el-icon>
        <el-button v-if="isStreaming && canStopExecute" type="danger" size="small" :icon="VideoPause"
          @click="emit('stopExecute')">
          停止
        </el-button>
      </div>
    </div>
    <div v-if="title && stepLabel" class="execute-card__subtitle">{{ title }}</div>
    <pre v-if="command" class="execute-card__code"><code>{{ command }}</code></pre>
    <MarkdownContent v-else-if="body" class="execute-card__content" mode="markdown" :content="body" />
  </div>
</template>

<style scoped>
.execute-card {
  display: grid;
  gap: 10px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.execute-card--step {
  background: rgba(8, 47, 73, 0.28);
}

.execute-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.execute-card__title {
  font-size: var(--font-size-sm);
  font-weight: 700;
  letter-spacing: 0.06em;
  color: rgba(191, 219, 254, 0.88);
  text-transform: uppercase;
}

.execute-card__actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.execute-card__loading {
  font-size: var(--font-size-md);
  color: var(--color-accent-secondary);
  animation: spin 1s linear infinite;
}

.execute-card__subtitle {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.execute-card__code {
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

.execute-card__content {
  line-height: 1.6;
  overflow-wrap: anywhere;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
