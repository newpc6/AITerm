<script setup lang="ts">
import { computed, ref, watch, onUnmounted } from 'vue'
import { Loading, ArrowDown, ArrowUp } from '@element-plus/icons-vue'
import MarkdownContent from '@/components/MarkdownContent.vue'

interface MessageMetadata {
  thinking?: string
  reasoning_duration?: number
  total_duration?: number
  [key: string]: unknown
}

const props = defineProps<{
  content: string
  role: 'user' | 'assistant'
  isStreaming?: boolean
  isReasoningActive?: boolean
  metadata?: MessageMetadata
}>()

const thinkingPattern = /<thinking(?:\s+duration="([\d.]+)")?[^>]*>\n?([\s\S]*?)\n?<\/thinking>\n?\n?/

const parsedContent = computed(() => {
  if (props.metadata?.thinking) {
    return {
      thinking: props.metadata.thinking,
      duration: props.metadata.reasoning_duration || 0,
      content: props.content,
      totalDuration: props.metadata.total_duration || 0,
    }
  }

  try {
    const parsed = JSON.parse(props.content)
    if (typeof parsed === 'object' && parsed !== null) {
      if (typeof parsed.answer === 'string') {
        return {
          thinking: parsed.thinking || '',
          duration: parsed.reasoning_duration || 0,
          content: parsed.answer,
          totalDuration: parsed.total_duration || 0,
        }
      }
      if (typeof parsed.content === 'string' && typeof parsed.type === 'string') {
        return {
          thinking: '',
          duration: 0,
          content: parsed.content,
          totalDuration: 0,
        }
      }
    }
  } catch {
    // JSON 解析失败，尝试旧格式
  }

  const match = props.content.match(thinkingPattern)
  if (match) {
    return {
      thinking: match[2].trim(),
      duration: match[1] ? parseFloat(match[1]) : 0,
      content: props.content.replace(thinkingPattern, ''),
      totalDuration: 0,
    }
  }

  return {
    thinking: '',
    duration: 0,
    content: props.content,
    totalDuration: 0,
  }
})

const showThinking = computed(() => parsedContent.value.thinking.length > 0)
const isThinkingExpanded = ref(true)
const liveDuration = ref(0)
let durationTimer: ReturnType<typeof setInterval> | null = null

const isThinkingActive = computed(() => props.isReasoningActive && parsedContent.value.thinking.length > 0 && parsedContent.value.duration === 0)

function toggleThinking() {
  isThinkingExpanded.value = !isThinkingExpanded.value
}

function formatDuration(seconds: number): string {
  if (seconds < 1) {
    return '不到 1 秒'
  }
  return `${seconds.toFixed(1)} 秒`
}

watch(isThinkingActive, (active) => {
  if (active) {
    liveDuration.value = 0
    durationTimer = setInterval(() => {
      liveDuration.value += 0.1
    }, 100)
  } else {
    if (durationTimer) {
      clearInterval(durationTimer)
      durationTimer = null
    }
  }
}, { immediate: true })

onUnmounted(() => {
  if (durationTimer) {
    clearInterval(durationTimer)
  }
})
</script>

<template>
  <div class="message-content-wrapper">
    <div v-if="showThinking" class="thinking-block">
      <div class="thinking-header" @click="toggleThinking">
        <span class="thinking-label">
          <template v-if="isThinkingActive">思考中 {{ formatDuration(liveDuration) }}</template>
          <template v-else>已思考 {{ formatDuration(parsedContent.duration || liveDuration) }}</template>
        </span>
        <el-icon class="thinking-toggle">
          <ArrowUp v-if="isThinkingExpanded" />
          <ArrowDown v-else />
        </el-icon>
      </div>
      <div v-show="isThinkingExpanded" class="thinking-body">
        <div class="thinking-line">
          <div class="thinking-dot"></div>
          <div class="thinking-line-vertical"></div>
        </div>
        <div class="thinking-content">
          <MarkdownContent :content="parsedContent.thinking" mode="plain" />
        </div>
      </div>
    </div>
    <MarkdownContent class="message-content" :mode="role === 'assistant' ? 'markdown' : 'auto'"
      :content="parsedContent.content" />
    <el-icon v-if="isStreaming" class="message-content__loading is-loading">
      <Loading />
    </el-icon>
  </div>
</template>

<style scoped>
.message-content-wrapper {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message-content {
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.message-content__loading {
  font-size: 14px;
  color: #60a5fa;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

.thinking-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  user-select: none;
  padding: 4px 0;
}

.thinking-header:hover .thinking-label {
  color: rgba(255, 255, 255, 0.9);
}

.thinking-label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
  font-weight: 500;
}

.thinking-toggle {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  transition: transform 0.2s;
}

.thinking-body {
  display: flex;
  gap: 8px;
}

.thinking-line {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 12px;
  flex-shrink: 0;
  padding-top: 4px;
}

.thinking-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.4);
  flex-shrink: 0;
}

.thinking-line-vertical {
  width: 2px;
  flex: 1;
  min-height: 20px;
  background: rgba(255, 255, 255, 0.2);
  margin-top: 4px;
}

.thinking-content {
  flex: 1;
  padding: 0 0 8px 0;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.55);
  line-height: 1.6;
  white-space: pre-wrap;
}
</style>
