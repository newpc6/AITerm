<script setup lang="ts">
import { Loading } from '@element-plus/icons-vue'
import MarkdownContent from '@/components/MarkdownContent.vue'

defineProps<{
  kind: 'summary' | 'repair' | 'info' | 'analysis' | 'retry' | 'output' | 'error' | 'result'
  title?: string
  body?: string
  isStreaming?: boolean
}>()

const kindStyles: Record<string, string> = {
  summary: 'execute-info-card--summary',
  repair: 'execute-info-card--repair',
  info: 'execute-info-card--info',
  analysis: 'execute-info-card--analysis',
  retry: 'execute-info-card--retry',
  output: 'execute-info-card--output',
  error: 'execute-info-card--error',
  result: 'execute-info-card--result',
}
</script>

<template>
  <div class="execute-info-card" :class="kindStyles[kind]">
    <div class="execute-info-card__header">
      <div class="execute-info-card__title">{{ title }}</div>
      <el-icon v-if="isStreaming" class="execute-info-card__loading is-loading">
        <Loading />
      </el-icon>
    </div>
    <MarkdownContent v-if="body" class="execute-info-card__content" mode="markdown" :content="body" />
  </div>
</template>

<style scoped>
.execute-info-card {
  display: grid;
  gap: 10px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.execute-info-card--summary {
  background: rgba(88, 28, 135, 0.22);
}

.execute-info-card--repair {
  background: rgba(120, 53, 15, 0.24);
}

.execute-info-card--info {
  background: var(--color-info);
}

.execute-info-card--analysis {
  background: rgba(30, 64, 175, 0.18);
}

.execute-info-card--retry {
  background: rgba(120, 53, 15, 0.24);
}

.execute-info-card--output {
  background: rgba(6, 78, 59, 0.22);
}

.execute-info-card--error {
  background: var(--color-danger-bg);
  border-color: var(--color-danger-border);
}

.execute-info-card--result {
  background: rgba(6, 78, 59, 0.22);
}

.execute-info-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.execute-info-card__title {
  font-size: var(--font-size-sm);
  font-weight: 700;
  letter-spacing: 0.06em;
  color: rgba(191, 219, 254, 0.88);
  text-transform: uppercase;
}

.execute-info-card__loading {
  font-size: var(--font-size-md);
  color: var(--color-accent-secondary);
  animation: spin 1s linear infinite;
}

.execute-info-card__content {
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
