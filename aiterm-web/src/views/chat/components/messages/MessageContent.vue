<script setup lang="ts">
import { computed, ref, watch, onUnmounted } from 'vue'
import { Loading, ArrowDown, ArrowUp, Tools } from '@element-plus/icons-vue'
import MarkdownContent from '@/components/MarkdownContent.vue'

interface ToolCall {
  name: string
  arguments: string
  result: string
  success: boolean
}

interface MessageMetadata {
  thinking?: string
  reasoning_duration?: number
  total_duration?: number
  tool_calls?: ToolCall[]
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
  if (props.metadata?.thinking || (props.metadata?.tool_calls && Array.isArray(props.metadata.tool_calls) && props.metadata.tool_calls.length > 0)) {
    return {
      thinking: props.metadata.thinking || '',
      duration: props.metadata.reasoning_duration || 0,
      content: props.content,
      totalDuration: props.metadata.total_duration || 0,
      toolCalls: Array.isArray(props.metadata.tool_calls) ? props.metadata.tool_calls : [],
    }
  }

  try {
    const parsed = JSON.parse(props.content)
    if (typeof parsed === 'object' && parsed !== null) {
      if (typeof parsed.answer === 'string') {
        const toolCalls = parsed.tool_calls
        return {
          thinking: parsed.thinking || '',
          duration: parsed.reasoning_duration || 0,
          content: parsed.answer,
          totalDuration: parsed.total_duration || 0,
          toolCalls: toolCalls && Array.isArray(toolCalls) && toolCalls.length > 0 ? toolCalls : [],
        }
      }
      if (typeof parsed.content === 'string' && typeof parsed.type === 'string') {
        return {
          thinking: '',
          duration: 0,
          content: parsed.content,
          totalDuration: 0,
          toolCalls: [],
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
      toolCalls: [],
    }
  }

  return {
    thinking: '',
    duration: 0,
    content: props.content,
    totalDuration: 0,
    toolCalls: [],
  }
})

const showThinking = computed(() => parsedContent.value.thinking.length > 0)
const showToolCalls = computed(() => parsedContent.value.toolCalls && parsedContent.value.toolCalls.length > 0)
const isThinkingExpanded = ref(true)
const isToolCallsExpanded = ref(true)
const liveDuration = ref(0)
let durationTimer: ReturnType<typeof setInterval> | null = null

const isThinkingActive = computed(() => props.isReasoningActive && parsedContent.value.thinking.length > 0 && parsedContent.value.duration === 0)

function toggleThinking() {
  isThinkingExpanded.value = !isThinkingExpanded.value
}

function toggleToolCalls() {
  isToolCallsExpanded.value = !isToolCallsExpanded.value
}

function formatDuration(seconds: number): string {
  if (seconds < 1) {
    return '不到 1 秒'
  }
  return `${seconds.toFixed(1)} 秒`
}

function formatToolArguments(args: string): string {
  try {
    const parsed = JSON.parse(args)
    return JSON.stringify(parsed, null, 2)
  } catch {
    return args
  }
}

function formatToolResult(result: string): string {
  try {
    const parsed = JSON.parse(result)
    return JSON.stringify(parsed, null, 2)
  } catch {
    return result
  }
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
    <div v-if="showToolCalls" class="tool-calls-block">
      <div class="tool-calls-header" @click="toggleToolCalls">
        <el-icon class="tool-calls-icon">
          <Tools />
        </el-icon>
        <span class="tool-calls-label">工具调用 ({{ parsedContent.toolCalls.length }})</span>
        <el-icon class="tool-calls-toggle">
          <ArrowUp v-if="isToolCallsExpanded" />
          <ArrowDown v-else />
        </el-icon>
      </div>
      <div v-show="isToolCallsExpanded" class="tool-calls-body">
        <div v-for="(tool, index) in parsedContent.toolCalls" :key="index" class="tool-call-item">
          <div class="tool-call-name">
            <span class="tool-call-index">{{ index + 1 }}</span>
            {{ tool.name }}
            <span :class="['tool-call-status', tool.success ? 'success' : 'error']">
              {{ tool.success ? '成功' : '失败' }}
            </span>
          </div>
          <div class="tool-call-details">
            <div class="tool-call-section">
              <div class="tool-call-section-label">输入参数</div>
              <pre class="tool-call-code">{{ formatToolArguments(tool.arguments) }}</pre>
            </div>
            <div class="tool-call-section">
              <div class="tool-call-section-label">返回结果</div>
              <pre class="tool-call-code">{{ formatToolResult(tool.result) }}</pre>
            </div>
          </div>
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

.tool-calls-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 8px;
}

.tool-calls-header {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  user-select: none;
  padding: 4px 0;
}

.tool-calls-header:hover .tool-calls-label {
  color: rgba(255, 255, 255, 0.9);
}

.tool-calls-icon {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
}

.tool-calls-label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
  font-weight: 500;
}

.tool-calls-toggle {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  transition: transform 0.2s;
}

.tool-calls-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-left: 4px;
}

.tool-call-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.tool-call-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.85);
}

.tool-call-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  font-size: 11px;
  color: rgba(255, 255, 255, 0.7);
}

.tool-call-status {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 400;
}

.tool-call-status.success {
  background: rgba(52, 211, 153, 0.15);
  color: #34d399;
}

.tool-call-status.error {
  background: rgba(248, 113, 113, 0.15);
  color: #f87171;
}

.tool-call-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tool-call-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tool-call-section-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.tool-call-code {
  margin: 0;
  padding: 8px 10px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 6px;
  font-size: 12px;
  font-family: 'Fira Code', 'Monaco', 'Consolas', monospace;
  color: rgba(255, 255, 255, 0.75);
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
}
</style>
