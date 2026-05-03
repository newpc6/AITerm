<script setup lang="ts">
import { computed, ref, onMounted, nextTick, watch } from 'vue'
import { MdPreview, Themes } from 'md-editor-v3'
import 'md-editor-v3/lib/preview.css'

const props = defineProps<{
  content: string
  mode?: 'auto' | 'markdown' | 'plain'
}>()

const plainTextPattern = /(^|\n)(#{1,6}\s|#{1,6}\S|\d+\.\s|[-*+]\s|>\s|```)|`[^`\r\n]+`|\[[^\]]+\]\([^)]+\)|\|.+\|/
const normalizedContent = computed(() => props.content.trim())
const shouldRenderMarkdown = computed(() => {
  if (props.mode === 'markdown') {
    return true
  }
  if (props.mode === 'plain') {
    return false
  }
  return plainTextPattern.test(normalizedContent.value)
})

const editorId = computed(() => `md-preview-${Math.random().toString(36).slice(2, 9)}`)
const theme = ref<Themes>('dark')

const expandAllCodeBlocks = () => {
  nextTick(() => {
    const details = document.querySelectorAll(`#${editorId.value} .md-editor-code details`)
    details.forEach((detail) => {
      (detail as HTMLDetailsElement).open = true
    })
  })
}

onMounted(() => {
  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
  theme.value = mediaQuery.matches ? 'dark' : 'light'

  mediaQuery.addEventListener('change', (e) => {
    theme.value = e.matches ? 'dark' : 'light'
  })

  expandAllCodeBlocks()
})

watch(() => props.content, () => {
  expandAllCodeBlocks()
})
</script>

<template>
  <div v-if="shouldRenderMarkdown" class="markdown-content">
    <MdPreview :id="editorId" :model-value="normalizedContent" :theme="theme" preview-theme="github-dark"
      code-theme="github-dark" :code-foldable="true" :auto-fold-threshold="150" />
  </div>
  <div v-else class="markdown-content markdown-content--plain">{{ normalizedContent }}</div>
</template>

<style scoped>
.markdown-content {
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.markdown-content :deep(.md-editor) {
  --md-color: rgba(255, 255, 255, 0.85);
  background: var(--color-border-secondary);
}

.markdown-content--plain {
  display: block;
  white-space: pre-wrap;
}

.markdown-content :deep(.md-editor-preview) {
  --md-color: rgba(255, 255, 255, 0.85);
  color: rgba(255, 255, 255, 0.85) !important;
  background: var(--color-border-secondary) !important;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
  padding: var(--spacing-lg) !important;
}

.markdown-content :deep(.md-preview-wrapper) {
  padding: 0 !important;
}

.markdown-content :deep(.md-preview-content) {
  padding: 0 !important;
}

.markdown-content :deep(.md-editor-preview p),
.markdown-content :deep(.md-editor-preview ul),
.markdown-content :deep(.md-editor-preview ol),
.markdown-content :deep(.md-editor-preview pre),
.markdown-content :deep(.md-editor-preview blockquote),
.markdown-content :deep(.md-editor-preview table),
.markdown-content :deep(.md-editor-preview div) {
  margin: 0;
  background: transparent !important;
  max-width: 100%;
}

.markdown-content :deep(.md-editor-preview p+p),
.markdown-content :deep(.md-editor-preview p+ul),
.markdown-content :deep(.md-editor-preview p+ol),
.markdown-content :deep(.md-editor-preview p+pre),
.markdown-content :deep(.md-editor-preview p+blockquote),
.markdown-content :deep(.md-editor-preview p+table),
.markdown-content :deep(.md-editor-preview ul+p),
.markdown-content :deep(.md-editor-preview ol+p),
.markdown-content :deep(.md-editor-preview pre+p),
.markdown-content :deep(.md-editor-preview blockquote+p),
.markdown-content :deep(.md-editor-preview table+p),
.markdown-content :deep(.md-editor-preview ul+ul),
.markdown-content :deep(.md-editor-preview ul+ol),
.markdown-content :deep(.md-editor-preview ol+ul),
.markdown-content :deep(.md-editor-preview ol+ol),
.markdown-content :deep(.md-editor-preview pre+pre),
.markdown-content :deep(.md-editor-preview blockquote+blockquote),
.markdown-content :deep(.md-editor-preview table+table),
.markdown-content :deep(.md-editor-preview ul+pre),
.markdown-content :deep(.md-editor-preview ol+pre),
.markdown-content :deep(.md-editor-preview pre+ul),
.markdown-content :deep(.md-editor-preview pre+ol) {
  margin-top: 10px;
}

.markdown-content :deep(.md-editor-preview ul),
.markdown-content :deep(.md-editor-preview ol) {
  padding-left: 20px;
}

.markdown-content :deep(.md-editor-preview li) {}

.markdown-content :deep(.md-editor-preview code) {
  padding: 2px 6px;
  border-radius: 6px;
  background: var(--color-bg-input) !important;
  font-family: Consolas, 'Courier New', monospace;
  font-size: 0.95em;
}

.markdown-content :deep(.md-editor-preview pre) {
  padding: 12px 14px;
  border-radius: 14px;
  background: var(--color-bg-input) !important;
  border: 1px solid var(--color-border-primary);
  overflow: auto;
  margin: 0 !important;
}

.markdown-content :deep(.md-editor-preview pre code) {
  padding: 0;
  background: transparent !important;
  white-space: pre-wrap;
  word-break: break-all;
}

.markdown-content :deep(.md-editor-preview .md-editor-code [rn-wrapper]) {
  inset-block-start: 0 !important;
}

.markdown-content :deep(.md-editor-preview blockquote) {
  padding: 8px 12px;
  border-left: 3px solid var(--color-border-focus);
  color: var(--color-text-tertiary) !important;
  background: transparent !important;
  margin: 0;
}

.markdown-content :deep(.md-editor-preview blockquote *) {
  color: var(--color-text-tertiary) !important;
}

.markdown-content :deep(.md-editor-preview table) {
  width: 100%;
  border-collapse: collapse;
}

.markdown-content :deep(.md-editor-preview th),
.markdown-content :deep(.md-editor-preview td) {
  padding: 8px 10px;
  border: 1px solid var(--color-border-primary);
  text-align: left;
  color: var(--color-text-secondary) !important;
}

.markdown-content :deep(.md-editor-preview table tr:nth-child(2n)) {
  background: transparent !important;
}

.markdown-content :deep(.md-editor-preview a) {
  color: var(--color-accent-secondary) !important;
}

.markdown-content :deep(.md-editor-preview h1),
.markdown-content :deep(.md-editor-preview h2),
.markdown-content :deep(.md-editor-preview h3),
.markdown-content :deep(.md-editor-preview h4),
.markdown-content :deep(.md-editor-preview h5),
.markdown-content :deep(.md-editor-preview h6) {
  color: var(--color-text-primary) !important;
  border-bottom: none;
  margin: 0;
}

.markdown-content :deep(.md-editor-preview h1+p),
.markdown-content :deep(.md-editor-preview h2+p),
.markdown-content :deep(.md-editor-preview h3+p),
.markdown-content :deep(.md-editor-preview h4+p),
.markdown-content :deep(.md-editor-preview h5+p),
.markdown-content :deep(.md-editor-preview h6+p) {
  margin-top: 8px;
}

.markdown-content :deep(.md-editor-preview .github-dark) {
  background: transparent !important;
}

.markdown-content :deep(.md-editor-preview .github-dark .code-line) {
  background: transparent !important;
  min-height: auto !important;
}

.markdown-content :deep(.md-editor-preview .github-dark .code-line:hover) {
  background: var(--color-bg-card-hover) !important;
}

.markdown-content :deep(.md-editor-preview .github-dark .code-line code) {
  color: var(--color-text-secondary) !important;
}

.markdown-content :deep(.md-editor-preview .github-dark .token.comment),
.markdown-content :deep(.md-editor-preview .github-dark .token.prolog),
.markdown-content :deep(.md-editor-preview .github-dark .token.doctype),
.markdown-content :deep(.md-editor-preview .github-dark .token.cdata) {
  color: var(--color-text-muted) !important;
}

.markdown-content :deep(.md-editor-preview .github-dark .token.punctuation) {
  color: var(--color-text-secondary) !important;
}

.markdown-content :deep(.md-editor-preview .github-dark .token.property),
.markdown-content :deep(.md-editor-preview .github-dark .token.tag),
.markdown-content :deep(.md-editor-preview .github-dark .token.boolean),
.markdown-content :deep(.md-editor-preview .github-dark .token.number),
.markdown-content :deep(.md-editor-preview .github-dark .token.constant),
.markdown-content :deep(.md-editor-preview .github-dark .token.symbol),
.markdown-content :deep(.md-editor-preview .github-dark .token.deleted) {
  color: #f97583 !important;
}

.markdown-content :deep(.md-editor-preview .github-dark .token.selector),
.markdown-content :deep(.md-editor-preview .github-dark .token.attr-name),
.markdown-content :deep(.md-editor-preview .github-dark .token.string),
.markdown-content :deep(.md-editor-preview .github-dark .token.char),
.markdown-content :deep(.md-editor-preview .github-dark .token.builtin),
.markdown-content :deep(.md-editor-preview .github-dark .token.inserted) {
  color: #9ecbff !important;
}

.markdown-content :deep(.md-editor-preview .github-dark .token.operator),
.markdown-content :deep(.md-editor-preview .github-dark .token.entity),
.markdown-content :deep(.md-editor-preview .github-dark .token.url),
.markdown-content :deep(.md-editor-preview .github-dark .language-css .token.string),
.markdown-content :deep(.md-editor-preview .github-dark .style .token.string) {
  color: var(--color-text-secondary) !important;
}

.markdown-content :deep(.md-editor-preview .github-dark .token.atrule),
.markdown-content :deep(.md-editor-preview .github-dark .token.attr-value),
.markdown-content :deep(.md-editor-preview .github-dark .token.keyword) {
  color: #ff7b72 !important;
}

.markdown-content :deep(.md-editor-preview .github-dark .token.function) {
  color: #d2a8ff !important;
}

.markdown-content :deep(.md-editor-preview .github-dark .token.regex),
.markdown-content :deep(.md-editor-preview .github-dark .token.important),
.markdown-content :deep(.md-editor-preview .github-dark .token.variable) {
  color: #79c0ff !important;
}

.markdown-content :deep(.md-editor-preview .github-dark .token.class-name) {
  color: #ffa657 !important;
}

.markdown-content :deep(.md-editor-preview strong) {
  color: var(--color-text-primary) !important;
  font-weight: 600;
}

.markdown-content :deep(.md-editor-preview em) {
  color: var(--color-text-secondary) !important;
  font-style: italic;
}

.markdown-content :deep(.md-editor-preview hr) {
  border: none;
  border-top: 1px solid var(--color-border-primary);
  margin: 10px 0;
}

.markdown-content :deep(.md-editor-preview img) {
  max-width: 100%;
  border-radius: 8px;
}
</style>
