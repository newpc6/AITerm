<script setup lang="ts">
import MarkdownContent from '@/components/MarkdownContent.vue'

defineProps<{
  title?: string
  body?: string
}>()
</script>

<template>
  <div class="execute-card execute-card--plan">
    <div class="execute-card__title">{{ title || '步骤规划' }}</div>
    <pre v-if="body" class="execute-card__code"><code>{{ body }}</code></pre>
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

.execute-card--plan {
  background: rgba(30, 64, 175, 0.18);
}

.execute-card__title {
  font-size: var(--font-size-sm);
  font-weight: 700;
  letter-spacing: 0.06em;
  color: rgba(191, 219, 254, 0.88);
  text-transform: uppercase;
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
</style>
