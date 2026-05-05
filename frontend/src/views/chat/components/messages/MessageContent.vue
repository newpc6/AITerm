<script setup lang="ts">
import { computed, ref, watch, onUnmounted } from 'vue'
import { Loading, ArrowDown, ArrowUp, Tools, Document, CircleCheck } from '@element-plus/icons-vue'
import MarkdownContent from '@/components/MarkdownContent.vue'

interface ToolCall {
  name: string
  arguments: string
  result: string
  success: boolean
  timestamp?: string
}

interface IterationInfo {
  thinking?: string
  thinking_duration?: number
  thinking_start_time?: string
  tool_calls?: ToolCall[]
  input?: string
  full_input?: string
  content?: string
}

interface MessageMetadata {
  thinking?: string
  reasoning_duration?: number
  total_duration?: number
  tool_calls?: ToolCall[]
  iterations?: IterationInfo[]
  current_thinking?: string
  [key: string]: unknown
}

const props = defineProps<{
  content: string
  role: 'user' | 'assistant'
  isStreaming?: boolean
  isReasoningActive?: boolean
  metadata?: MessageMetadata
  displaySettings?: {
    showThinking: boolean
    expandThinking: boolean
    showTools: boolean
    expandTools: boolean
    showInput: boolean
    expandInput: boolean
    autoCollapse: boolean
  }
}>()

const thinkingPattern = /<thinking(?:\s+duration="([\d.]+)")?[^>]*>\n?([\s\S]*?)\n?<\/thinking>\n?\n?/

interface ParsedIteration {
  thinking: string
  thinkingDuration: number
  thinkingStartTime: string
  toolCalls: ToolCall[]
  input: string
  fullInput: string
  content: string
}

interface ParsedContent {
  content: string
  totalDuration: number
  iterations: ParsedIteration[]
  legacyThinking: string
  legacyThinkingDuration: number
  legacyToolCalls: ToolCall[]
  currentThinking: string
}

const parsedContent = computed<ParsedContent>(() => {
  if (props.metadata?.iterations && Array.isArray(props.metadata.iterations) && props.metadata.iterations.length > 0) {
    return {
      content: props.content,
      totalDuration: props.metadata.total_duration || 0,
      iterations: props.metadata.iterations.map(iter => ({
        thinking: iter.thinking || '',
        thinkingDuration: iter.thinking_duration || 0,
        thinkingStartTime: iter.thinking_start_time || '',
        toolCalls: iter.tool_calls || [],
        input: iter.input || '',
        fullInput: iter.full_input || '',
        content: iter.content || '',
      })),
      legacyThinking: '',
      legacyThinkingDuration: 0,
      legacyToolCalls: [],
      currentThinking: props.metadata.current_thinking || '',
    }
  }

  if (props.metadata?.thinking || (props.metadata?.tool_calls && Array.isArray(props.metadata.tool_calls) && props.metadata.tool_calls.length > 0)) {
    return {
      content: props.content,
      totalDuration: props.metadata.total_duration || 0,
      iterations: [],
      legacyThinking: props.metadata.thinking || '',
      legacyThinkingDuration: props.metadata.reasoning_duration || 0,
      legacyToolCalls: Array.isArray(props.metadata.tool_calls) ? props.metadata.tool_calls : [],
      currentThinking: props.metadata.current_thinking || '',
    }
  }

  try {
    const parsed = JSON.parse(props.content)
    if (typeof parsed === 'object' && parsed !== null) {
      if (typeof parsed.answer === 'string') {
        if (parsed.iterations && Array.isArray(parsed.iterations) && parsed.iterations.length > 0) {
          return {
            content: parsed.answer,
            totalDuration: parsed.total_duration || 0,
            iterations: parsed.iterations.map((iter: IterationInfo) => ({
              thinking: iter.thinking || '',
              thinkingDuration: iter.thinking_duration || 0,
              thinkingStartTime: iter.thinking_start_time || '',
              toolCalls: iter.tool_calls || [],
              input: iter.input || '',
              fullInput: iter.full_input || '',
              content: iter.content || '',
            })),
            legacyThinking: '',
            legacyThinkingDuration: 0,
            legacyToolCalls: [],
            currentThinking: '',
          }
        }

        const toolCalls = parsed.tool_calls
        return {
          content: parsed.answer,
          totalDuration: parsed.total_duration || 0,
          iterations: [],
          legacyThinking: parsed.thinking || '',
          legacyThinkingDuration: parsed.reasoning_duration || 0,
          legacyToolCalls: toolCalls && Array.isArray(toolCalls) && toolCalls.length > 0 ? toolCalls : [],
          currentThinking: '',
        }
      }
      if (typeof parsed.content === 'string' && typeof parsed.type === 'string') {
        return {
          content: parsed.content,
          totalDuration: 0,
          iterations: [],
          legacyThinking: '',
          legacyThinkingDuration: 0,
          legacyToolCalls: [],
          currentThinking: '',
        }
      }
    }
  } catch {
    // JSON 解析失败，尝试旧格式
  }

  const match = props.content.match(thinkingPattern)
  if (match) {
    return {
      content: props.content.replace(thinkingPattern, ''),
      totalDuration: 0,
      iterations: [],
      legacyThinking: match[2].trim(),
      legacyThinkingDuration: match[1] ? parseFloat(match[1]) : 0,
      legacyToolCalls: [],
      currentThinking: '',
    }
  }

  return {
    content: props.content,
    totalDuration: 0,
    iterations: [],
    legacyThinking: '',
    legacyThinkingDuration: 0,
    legacyToolCalls: [],
    currentThinking: '',
  }
})

const hasIterations = computed(() => parsedContent.value.iterations.length > 0)
const hasLegacyThinking = computed(() => parsedContent.value.legacyThinking.length > 0)
const hasLegacyToolCalls = computed(() => parsedContent.value.legacyToolCalls.length > 0)
const hasCurrentThinking = computed(() => parsedContent.value.currentThinking.length > 0)

const collapsedThinking = ref<Set<number>>(new Set())
const collapsedToolCalls = ref<Set<number>>(new Set())
const collapsedInput = ref<Set<number>>(new Set())
const manuallyExpandedThinking = ref<Set<number>>(new Set())
const manuallyExpandedToolCalls = ref<Set<number>>(new Set())
const manuallyExpandedInput = ref<Set<number>>(new Set())
const delayedCollapseToolCalls = ref<Set<number>>(new Set())
const delayedCollapseInput = ref<Set<number>>(new Set())
const alreadyCollapsedToolCalls = ref<Set<number>>(new Set())
const alreadyCollapsedInput = ref<Set<number>>(new Set())
const liveDuration = ref(0)
let durationTimer: ReturnType<typeof setInterval> | null = null
let collapseTimers: Map<string, ReturnType<typeof setTimeout>> = new Map()

const AUTO_COLLAPSE_DELAY = 1000

const isThinkingActive = computed(() => props.isReasoningActive && (hasLegacyThinking.value || hasCurrentThinking.value))

const settings = computed(() => props.displaySettings || {
  showThinking: true,
  expandThinking: false,
  showTools: true,
  expandTools: false,
  showInput: true,
  expandInput: false,
  autoCollapse: true,
})

function isThinkingInProgress(iteration?: ParsedIteration): boolean {
  if (!props.isStreaming) return false
  if (!iteration) return false
  return !!iteration.thinking && !iteration.thinkingDuration
}

function isToolCallsInProgress(iteration?: ParsedIteration): boolean {
  if (!props.isStreaming) return false
  if (!iteration || !iteration.toolCalls || iteration.toolCalls.length === 0) return false
  return iteration.toolCalls.some(tool => !tool.result)
}

function shouldShowThinking(): boolean {
  return settings.value.showThinking
}

function shouldShowTools(): boolean {
  return settings.value.showTools
}

function shouldShowInput(): boolean {
  return settings.value.showInput
}

function isThinkingExpanded(index: number, iteration?: ParsedIteration): boolean {
  if (manuallyExpandedThinking.value.has(index)) {
    return true
  }
  if (collapsedThinking.value.has(index)) {
    return false
  }
  if (props.isStreaming) {
    if (settings.value.autoCollapse) {
      if (isThinkingInProgress(iteration)) {
        return true
      }
      return false
    }
    return true
  }
  return settings.value.expandThinking
}

function isToolCallsExpanded(index: number, iteration?: ParsedIteration): boolean {
  if (manuallyExpandedToolCalls.value.has(index)) {
    return true
  }
  if (collapsedToolCalls.value.has(index)) {
    return false
  }
  if (props.isStreaming) {
    if (alreadyCollapsedToolCalls.value.has(index)) {
      return false
    }
    if (delayedCollapseToolCalls.value.has(index)) {
      return true
    }
    if (settings.value.autoCollapse) {
      if (isToolCallsInProgress(iteration)) {
        return true
      }
      if (iteration?.toolCalls && iteration.toolCalls.length > 0) {
        const allComplete = iteration.toolCalls.every(tool => tool.result)
        if (allComplete) {
          const timerKey = `tool-${index}`
          if (!collapseTimers.has(timerKey)) {
            delayedCollapseToolCalls.value.add(index)
            const timer = setTimeout(() => {
              delayedCollapseToolCalls.value.delete(index)
              alreadyCollapsedToolCalls.value.add(index)
              collapseTimers.delete(timerKey)
            }, AUTO_COLLAPSE_DELAY)
            collapseTimers.set(timerKey, timer)
          }
          return true
        }
      }
      return false
    }
    return true
  }
  return settings.value.expandTools
}

function isInputExpanded(index: number, iteration?: ParsedIteration): boolean {
  if (manuallyExpandedInput.value.has(index)) {
    return true
  }
  if (collapsedInput.value.has(index)) {
    return false
  }
  if (props.isStreaming) {
    if (alreadyCollapsedInput.value.has(index)) {
      return false
    }
    if (delayedCollapseInput.value.has(index)) {
      return true
    }
    if (settings.value.autoCollapse) {
      if (iteration?.input) {
        const timerKey = `input-${index}`
        if (!collapseTimers.has(timerKey)) {
          delayedCollapseInput.value.add(index)
          const timer = setTimeout(() => {
            delayedCollapseInput.value.delete(index)
            alreadyCollapsedInput.value.add(index)
            collapseTimers.delete(timerKey)
          }, AUTO_COLLAPSE_DELAY)
          collapseTimers.set(timerKey, timer)
        }
        return true
      }
      return false
    }
    return true
  }
  return settings.value.expandInput
}

function isLegacyThinkingExpanded(): boolean {
  if (manuallyExpandedThinking.value.has(-1)) {
    return true
  }
  if (collapsedThinking.value.has(-1)) {
    return false
  }
  if (props.isStreaming) {
    if (settings.value.autoCollapse) {
      return isThinkingActive.value
    }
    return true
  }
  return settings.value.expandThinking
}

function isLegacyToolCallsExpanded(): boolean {
  if (manuallyExpandedToolCalls.value.has(-1)) {
    return true
  }
  if (collapsedToolCalls.value.has(-1)) {
    return false
  }
  if (props.isStreaming) {
    if (alreadyCollapsedToolCalls.value.has(-1)) {
      return false
    }
    if (delayedCollapseToolCalls.value.has(-1)) {
      return true
    }
    if (settings.value.autoCollapse) {
      if (hasLegacyToolCalls.value) {
        const timerKey = 'legacy-tool'
        if (!collapseTimers.has(timerKey)) {
          delayedCollapseToolCalls.value.add(-1)
          const timer = setTimeout(() => {
            delayedCollapseToolCalls.value.delete(-1)
            alreadyCollapsedToolCalls.value.add(-1)
            collapseTimers.delete(timerKey)
          }, AUTO_COLLAPSE_DELAY)
          collapseTimers.set(timerKey, timer)
        }
        return true
      }
      return false
    }
    return true
  }
  return settings.value.expandTools
}

function isLegacyInputExpanded(): boolean {
  if (manuallyExpandedInput.value.has(-1)) {
    return true
  }
  if (collapsedInput.value.has(-1)) {
    return false
  }
  if (props.isStreaming) {
    if (alreadyCollapsedInput.value.has(-1)) {
      return false
    }
    if (delayedCollapseInput.value.has(-1)) {
      return true
    }
    if (settings.value.autoCollapse) {
      const timerKey = 'legacy-input'
      if (!collapseTimers.has(timerKey)) {
        delayedCollapseInput.value.add(-1)
        const timer = setTimeout(() => {
          delayedCollapseInput.value.delete(-1)
          alreadyCollapsedInput.value.add(-1)
          collapseTimers.delete(timerKey)
        }, AUTO_COLLAPSE_DELAY)
        collapseTimers.set(timerKey, timer)
      }
      return true
    }
    return true
  }
  return settings.value.expandInput
}

function toggleThinking(index: number) {
  if (collapsedThinking.value.has(index)) {
    collapsedThinking.value.delete(index)
    manuallyExpandedThinking.value.add(index)
  } else if (manuallyExpandedThinking.value.has(index)) {
    manuallyExpandedThinking.value.delete(index)
    collapsedThinking.value.add(index)
  } else {
    collapsedThinking.value.add(index)
  }
}

function toggleToolCalls(index: number) {
  if (collapsedToolCalls.value.has(index)) {
    collapsedToolCalls.value.delete(index)
    manuallyExpandedToolCalls.value.add(index)
    alreadyCollapsedToolCalls.value.delete(index)
  } else if (manuallyExpandedToolCalls.value.has(index)) {
    manuallyExpandedToolCalls.value.delete(index)
    collapsedToolCalls.value.add(index)
  } else {
    collapsedToolCalls.value.add(index)
  }
}

function toggleInput(index: number) {
  if (collapsedInput.value.has(index)) {
    collapsedInput.value.delete(index)
    manuallyExpandedInput.value.add(index)
    alreadyCollapsedInput.value.delete(index)
  } else if (manuallyExpandedInput.value.has(index)) {
    manuallyExpandedInput.value.delete(index)
    collapsedInput.value.add(index)
  } else {
    collapsedInput.value.add(index)
  }
}

function toggleLegacyThinking() {
  if (collapsedThinking.value.has(-1)) {
    collapsedThinking.value.delete(-1)
    manuallyExpandedThinking.value.add(-1)
  } else if (manuallyExpandedThinking.value.has(-1)) {
    manuallyExpandedThinking.value.delete(-1)
    collapsedThinking.value.add(-1)
  } else {
    collapsedThinking.value.add(-1)
  }
}

function toggleLegacyToolCalls() {
  if (collapsedToolCalls.value.has(-1)) {
    collapsedToolCalls.value.delete(-1)
    manuallyExpandedToolCalls.value.add(-1)
    alreadyCollapsedToolCalls.value.delete(-1)
  } else if (manuallyExpandedToolCalls.value.has(-1)) {
    manuallyExpandedToolCalls.value.delete(-1)
    collapsedToolCalls.value.add(-1)
  } else {
    collapsedToolCalls.value.add(-1)
  }
}

function toggleLegacyInput() {
  if (collapsedInput.value.has(-1)) {
    collapsedInput.value.delete(-1)
    manuallyExpandedInput.value.add(-1)
    alreadyCollapsedInput.value.delete(-1)
  } else if (manuallyExpandedInput.value.has(-1)) {
    manuallyExpandedInput.value.delete(-1)
    collapsedInput.value.add(-1)
  } else {
    collapsedInput.value.add(-1)
  }
}

function formatDuration(seconds: number): string {
  if (seconds < 1) {
    return '不到 1 秒'
  }
  return `${seconds.toFixed(1)} 秒`
}

function formatTime(timestamp: string): string {
  if (!timestamp) return ''
  try {
    const date = new Date(timestamp)
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hour = String(date.getHours()).padStart(2, '0')
    const minute = String(date.getMinutes()).padStart(2, '0')
    const second = String(date.getSeconds()).padStart(2, '0')
    return `${year}-${month}-${day} ${hour}:${minute}:${second}`
  } catch {
    return ''
  }
}

function formatToolArguments(args: string): string {
  try {
    const parsed = JSON.parse(args)
    return '```json\n' + JSON.stringify(parsed, null, 2) + '\n```'
  } catch {
    return '```\n' + args + '\n```'
  }
}

function formatToolResult(result: string): string {
  try {
    const parsed = JSON.parse(result)
    return '```json\n' + JSON.stringify(parsed, null, 2) + '\n```'
  } catch {
    if (result.length > 500) {
      return '```\n' + result.slice(0, 500) + '...\n```'
    }
    return '```\n' + result + '\n```'
  }
}

function getFirstToolName(iteration: ParsedIteration): string {
  if (iteration.toolCalls && iteration.toolCalls.length > 0) {
    return iteration.toolCalls[0].name
  }
  return '工具'
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
  collapseTimers.forEach(timer => clearTimeout(timer))
  collapseTimers.clear()
})
</script>

<template>
  <div class="message-content-wrapper">
    <template v-if="hasIterations">
      <div v-for="(iteration, index) in parsedContent.iterations" :key="index" class="iteration-block">
        <div v-if="shouldShowInput() && iteration.input" class="input-block">
          <div class="input-header" @click="toggleInput(index)">
            <el-icon class="input-icon">
              <Document />
            </el-icon>
            <span class="input-label">用户输入</span>
            <el-icon class="input-toggle">
              <ArrowUp v-if="isInputExpanded(index, iteration)" />
              <ArrowDown v-else />
            </el-icon>
          </div>
          <div v-show="isInputExpanded(index, iteration)" class="input-body">
            <MarkdownContent :content="'```json\n' + iteration.input + '\n```'" mode="markdown" />
          </div>
        </div>

        <div v-if="shouldShowInput() && iteration.fullInput" class="input-block full-input-block">
          <div class="input-header" @click="toggleInput(index)">
            <el-icon class="input-icon">
              <Document />
            </el-icon>
            <span class="input-label">完整输入（含提示词）</span>
            <el-icon class="input-toggle">
              <ArrowUp v-if="isInputExpanded(index, iteration)" />
              <ArrowDown v-else />
            </el-icon>
          </div>
          <div v-show="isInputExpanded(index, iteration)" class="input-body">
            <MarkdownContent :content="'```json\n' + iteration.fullInput + '\n```'" mode="markdown" />
          </div>
        </div>

        <div v-if="shouldShowThinking() && iteration.thinking" class="thinking-block"
          :class="{ 'thinking-active': !iteration.thinkingDuration && props.isReasoningActive }">
          <div class="thinking-header" @click="toggleThinking(index)">
            <el-icon v-if="!iteration.thinkingDuration && props.isReasoningActive"
              class="thinking-status-icon is-spinning">
              <Loading />
            </el-icon>
            <el-icon v-else class="thinking-status-icon is-completed">
              <CircleCheck />
            </el-icon>
            <span class="thinking-label">
              <template v-if="!iteration.thinkingDuration && props.isReasoningActive">思考中</template>
              <template v-else>已思考</template>
              <span v-if="iteration.thinkingDuration" class="thinking-duration">耗时 {{
                formatDuration(iteration.thinkingDuration)
              }}</span>
            </span>
            <span v-if="iteration.thinkingStartTime" class="thinking-time">{{ formatTime(iteration.thinkingStartTime)
            }}</span>
            <el-icon class="thinking-toggle">
              <ArrowUp v-if="isThinkingExpanded(index, iteration)" />
              <ArrowDown v-else />
            </el-icon>
          </div>
          <div v-show="isThinkingExpanded(index, iteration)" class="thinking-body">
            <div class="thinking-line">
              <div class="thinking-dot"></div>
              <div class="thinking-line-vertical"></div>
            </div>
            <div class="thinking-content">
              <MarkdownContent :content="iteration.thinking" mode="plain" />
            </div>
          </div>
        </div>

        <div v-if="shouldShowTools() && iteration.toolCalls && iteration.toolCalls.length > 0" class="tool-calls-block">
          <div class="tool-calls-header" @click="toggleToolCalls(index)">
            <el-icon class="tool-calls-icon">
              <Tools />
            </el-icon>
            <span class="tool-calls-label">
              调用工具 {{ getFirstToolName(iteration) }}
              <span v-if="iteration.toolCalls.length > 1">等 {{ iteration.toolCalls.length }} 个</span>
            </span>
            <span v-if="iteration.toolCalls[0]?.timestamp" class="tool-calls-time">{{
              formatTime(iteration.toolCalls[0].timestamp) }}</span>
            <el-icon class="tool-calls-toggle">
              <ArrowUp v-if="isToolCallsExpanded(index, iteration)" />
              <ArrowDown v-else />
            </el-icon>
          </div>
          <div v-show="isToolCallsExpanded(index, iteration)" class="tool-calls-body">
            <div v-for="(tool, toolIndex) in iteration.toolCalls" :key="toolIndex" class="tool-call-item">
              <div class="tool-call-name">
                {{ tool.name }}
                <span :class="['tool-call-status', tool.success ? 'success' : 'error']">
                  {{ tool.success ? '成功' : '失败' }}
                </span>
              </div>
              <div class="tool-call-details">
                <div class="tool-call-section">
                  <div class="tool-call-section-label">输入参数</div>
                  <MarkdownContent :content="formatToolArguments(tool.arguments)" mode="markdown" />
                </div>
                <div class="tool-call-section">
                  <div class="tool-call-section-label">返回结果</div>
                  <MarkdownContent :content="formatToolResult(tool.result)" mode="markdown" />
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="iteration.content" class="iteration-content">
          <MarkdownContent :content="iteration.content" mode="markdown" />
        </div>
      </div>
    </template>

    <template v-else>
      <div v-if="shouldShowThinking() && isThinkingActive && (hasLegacyThinking || hasCurrentThinking)"
        class="thinking-block thinking-active">
        <div class="thinking-header" @click="toggleLegacyThinking">
          <span class="thinking-label">
            思考中 {{ liveDuration > 0 ? formatDuration(liveDuration) : '' }}
          </span>
          <el-icon class="thinking-toggle">
            <ArrowUp v-if="isLegacyThinkingExpanded()" />
            <ArrowDown v-else />
          </el-icon>
        </div>
        <div v-show="isLegacyThinkingExpanded()" class="thinking-body">
          <div class="thinking-line">
            <div class="thinking-dot thinking-dot-active"></div>
            <div class="thinking-line-vertical"></div>
          </div>
          <div class="thinking-content">
            <MarkdownContent :content="parsedContent.currentThinking || parsedContent.legacyThinking" mode="plain" />
          </div>
        </div>
      </div>
      <div v-else-if="shouldShowThinking() && hasLegacyThinking" class="thinking-block">
        <div class="thinking-header" @click="toggleLegacyThinking">
          <span class="thinking-label">
            已思考
            <span v-if="parsedContent.legacyThinkingDuration" class="thinking-duration">耗时 {{
              formatDuration(parsedContent.legacyThinkingDuration) }}</span>
          </span>
          <el-icon class="thinking-toggle">
            <ArrowUp v-if="isLegacyThinkingExpanded()" />
            <ArrowDown v-else />
          </el-icon>
        </div>
        <div v-show="isLegacyThinkingExpanded()" class="thinking-body">
          <div class="thinking-line">
            <div class="thinking-dot"></div>
            <div class="thinking-line-vertical"></div>
          </div>
          <div class="thinking-content">
            <MarkdownContent :content="parsedContent.legacyThinking" mode="plain" />
          </div>
        </div>
      </div>
      <div v-if="shouldShowTools() && hasLegacyToolCalls" class="tool-calls-block">
        <div class="tool-calls-header" @click="toggleLegacyToolCalls">
          <el-icon class="tool-calls-icon">
            <Tools />
          </el-icon>
          <span class="tool-calls-label">
            调用工具 {{ parsedContent.legacyToolCalls[0]?.name || '工具' }}
            <span v-if="parsedContent.legacyToolCalls.length > 1">等 {{ parsedContent.legacyToolCalls.length }} 个</span>
          </span>
          <span v-if="parsedContent.legacyToolCalls[0]?.timestamp" class="tool-calls-time">{{
            formatTime(parsedContent.legacyToolCalls[0].timestamp) }}</span>
          <el-icon class="tool-calls-toggle">
            <ArrowUp v-if="isLegacyToolCallsExpanded()" />
            <ArrowDown v-else />
          </el-icon>
        </div>
        <div v-show="isLegacyToolCallsExpanded()" class="tool-calls-body">
          <div v-for="(tool, index) in parsedContent.legacyToolCalls" :key="index" class="tool-call-item">
            <div class="tool-call-name">
              {{ tool.name }}
              <span :class="['tool-call-status', tool.success ? 'success' : 'error']">
                {{ tool.success ? '成功' : '失败' }}
              </span>
            </div>
            <div class="tool-call-details">
              <div class="tool-call-section">
                <div class="tool-call-section-label">输入参数</div>
                <MarkdownContent :content="formatToolArguments(tool.arguments)" mode="markdown" />
              </div>
              <div class="tool-call-section">
                <div class="tool-call-section-label">返回结果</div>
                <MarkdownContent :content="formatToolResult(tool.result)" mode="markdown" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <MarkdownContent v-if="!hasIterations" class="message-content" :mode="role === 'assistant' ? 'markdown' : 'auto'"
      :content="parsedContent.content" />
    <el-icon v-if="isStreaming" class="message-content__loading is-loading">
      <Loading />
    </el-icon>
    <div v-else-if="role === 'assistant' && parsedContent.totalDuration > 0 && !isStreaming" class="total-duration">
      <span class="total-duration__label">总耗时</span>
      <span class="total-duration__value">{{ formatDuration(parsedContent.totalDuration) }}</span>
    </div>
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

.iteration-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.iteration-content {
  padding: 12px 0;
  border-top: 1px dashed rgba(255, 255, 255, 0.1);
  margin-top: 4px;
}

.iteration-content :deep(p:first-child) {
  margin-top: 0;
}

.iteration-content :deep(p:last-child) {
  margin-bottom: 0;
}

.input-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-header {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  user-select: none;
  padding: 4px 0;
}

.input-header:hover .input-label {
  color: rgba(255, 255, 255, 0.9);
}

.input-icon {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
}

.input-label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
  font-weight: 500;
}

.input-toggle {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  transition: transform 0.2s;
}

.input-body {
  padding-left: 4px;
}

.full-input-block {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed rgba(255, 255, 255, 0.1);
}

.thinking-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.thinking-status-icon {
  font-size: 14px;
}

.thinking-status-icon.is-spinning {
  color: #409eff;
  animation: spin 1s linear infinite;
}

.thinking-status-icon.is-completed {
  color: #67c23a;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

.thinking-active .thinking-dot-active {
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {

  0%,
  100% {
    opacity: 1;
  }

  50% {
    opacity: 0.4;
  }
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
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

.thinking-duration {
  color: rgba(255, 255, 255, 0.45);
  font-weight: 400;
  margin-left: 4px;
}

.thinking-time {
  font-size: 12px;
  margin-top: 4px;
  color: rgba(255, 255, 255, 0.4);
  margin-left: 8px;
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

.tool-calls-time {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  margin-left: 8px;
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

.total-duration {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed rgba(255, 255, 255, 0.1);
}

.total-duration__label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}

.total-duration__value {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  font-weight: 500;
}
</style>
