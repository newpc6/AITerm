<script setup lang="ts">
import { computed } from 'vue'

import { renderMarkdown } from '@/utils/markdown'

const props = defineProps<{
  content: string
}>()

const plainTextPattern = /(^|\n)(#{1,6}\s|\d+\.\s|[-*+]\s|>\s|```)|`[^`]+`|\[[^\]]+\]\([^)]+\)|\|.+\|/
const normalizedContent = computed(() => props.content.trim())
const shouldRenderMarkdown = computed(() => plainTextPattern.test(normalizedContent.value))
const renderedHtml = computed(() => renderMarkdown(props.content))
</script>

<template>
  <div v-if="shouldRenderMarkdown" class="markdown-content" v-html="renderedHtml"></div>
  <div v-else class="markdown-content markdown-content--plain">{{ normalizedContent }}</div>
</template>

<style scoped>
.markdown-content {
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.markdown-content--plain {
  display: block;
  white-space: pre-wrap;
}

.markdown-content :deep(*) {
  max-width: 100%;
}

.markdown-content :deep(p),
.markdown-content :deep(ul),
.markdown-content :deep(ol),
.markdown-content :deep(pre),
.markdown-content :deep(blockquote),
.markdown-content :deep(table) {
  margin: 0 0 12px;
}

.markdown-content :deep(p:last-child),
.markdown-content :deep(ul:last-child),
.markdown-content :deep(ol:last-child),
.markdown-content :deep(pre:last-child),
.markdown-content :deep(blockquote:last-child),
.markdown-content :deep(table:last-child) {
  margin-bottom: 0;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  padding-left: 20px;
}

.markdown-content :deep(code) {
  padding: 2px 6px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.08);
  font-family: Consolas, 'Courier New', monospace;
  font-size: 0.95em;
}

.markdown-content :deep(pre) {
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.08);
  overflow: auto;
}

.markdown-content :deep(pre code) {
  padding: 0;
  background: transparent;
}

.markdown-content :deep(blockquote) {
  padding-left: 12px;
  border-left: 3px solid rgba(255, 255, 255, 0.22);
  color: rgba(255, 255, 255, 0.72);
}

.markdown-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  padding: 8px 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  text-align: left;
}

.markdown-content :deep(a) {
  color: #7dd3fc;
}
</style>
