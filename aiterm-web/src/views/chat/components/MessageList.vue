<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { CopyDocument, RefreshRight } from '@element-plus/icons-vue'

import MarkdownContent from '@/components/MarkdownContent.vue'
import type { ChatMessage } from '@/types/chat'

const props = defineProps<{
  actionableMessageIds?: string[]
  assistantLabel: string
  assistantTitle?: string
  messages: ChatMessage[]
  retryableMessageIds?: string[]
  taskApprovalHint?: string
  taskApprovalLoading?: boolean
  taskApprovalMessageId?: string
  userLabel?: string
  userTitle?: string
}>()

const emit = defineEmits<{
  copy: [messageId: string]
  retry: [messageId: string]
  taskConfirm: [approved: boolean]
}>()

const containerRef = ref<HTMLDivElement | null>(null)
const autoScrollEnabled = ref(true)
const scrollThreshold = 32

const actionableMessageIdSet = computed(() => new Set(props.actionableMessageIds ?? []))
const retryableMessageIdSet = computed(() => new Set(props.retryableMessageIds ?? []))
const messageSignature = computed(() =>
  [
    props.messages.map((message) => `${message.id}:${message.role}:${message.content}:${message.createdAt}`).join('\n<aiterm-message>\n'),
    Array.from(actionableMessageIdSet.value).join(','),
    Array.from(retryableMessageIdSet.value).join(','),
  ].join('\n<aiterm-state>\n'),
)

function formatMessageTime(value: string) {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return '--:--'
  }

  const year = parsed.getFullYear()
  const month = `${parsed.getMonth() + 1}`.padStart(2, '0')
  const day = `${parsed.getDate()}`.padStart(2, '0')
  const hours = `${parsed.getHours()}`.padStart(2, '0')
  const minutes = `${parsed.getMinutes()}`.padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}`
}

function canRetry(message: ChatMessage) {
  return message.role === 'assistant' && retryableMessageIdSet.value.has(message.id)
}

function canShowActions(message: ChatMessage) {
  return message.role === 'assistant' && actionableMessageIdSet.value.has(message.id) && !!message.content
}

function canShowTaskApproval(message: ChatMessage) {
  return message.role === 'assistant' && !!message.content && props.taskApprovalMessageId === message.id
}

function isTaskPlanMessage(message: ChatMessage) {
  return message.role === 'assistant' && message.content.includes('任务计划如下') && message.content.includes('\n')
}

type TaskStructuredMessage = {
  kind: 'plan' | 'step-start' | 'step-result' | 'summary' | 'repair' | 'info'
  title?: string
  stepLabel?: string
  body?: string
  command?: string
}

function parseTaskStructuredMessage(content: string): TaskStructuredMessage | null {
  const normalized = content.trim()
  if (!normalized) {
    return null
  }

  if (normalized.startsWith('任务计划如下：')) {
    return {
      kind: 'plan',
      title: '执行计划',
      body: normalized.replace(/^任务计划如下：\s*/, ''),
    }
  }

  const stepStartMatch = normalized.match(/^开始执行第\s*(\d+)\s*步[:：]\s*(.+?)\n命令[:：]\s*([\s\S]+)$/)
  if (stepStartMatch) {
    return {
      kind: 'step-start',
      stepLabel: `第 ${stepStartMatch[1]} 步`,
      title: stepStartMatch[2].trim(),
      command: stepStartMatch[3].trim(),
    }
  }

  const stepResultMatch = normalized.match(/^第\s*(\d+)\s*步执行结果[:：]\s*\n?([\s\S]+)$/)
  if (stepResultMatch) {
    return {
      kind: 'step-result',
      stepLabel: `第 ${stepResultMatch[1]} 步结果`,
      body: stepResultMatch[2].trim(),
    }
  }

  if (normalized.startsWith('任务最终结果：')) {
    return {
      kind: 'summary',
      title: '最终结论',
      body: normalized.replace(/^任务最终结果：\s*/, ''),
    }
  }

  if (normalized.startsWith('失败复盘：') || normalized.includes('自动复盘')) {
    return {
      kind: 'repair',
      title: '自动复盘',
      body: normalized,
    }
  }

  if (normalized.startsWith('已生成 ') || normalized.includes('需要人工确认')) {
    return {
      kind: 'info',
      title: '任务提示',
      body: normalized,
    }
  }

  return null
}

function getTaskPlanIntro(content: string) {
  const parts = content.split('\n')
  return parts.shift()?.trim() ?? content.trim()
}

function getTaskPlanCode(content: string) {
  const parts = content.split('\n')
  parts.shift()
  return parts.join('\n').trim()
}

function isNearBottom(element: HTMLDivElement) {
  return element.scrollHeight - element.scrollTop - element.clientHeight <= scrollThreshold
}

function handleScroll() {
  if (!containerRef.value) {
    return
  }
  autoScrollEnabled.value = isNearBottom(containerRef.value)
}

function scrollToBottom() {
  if (!containerRef.value) {
    return
  }
  containerRef.value.scrollTop = containerRef.value.scrollHeight
}

watch(
  messageSignature,
  async () => {
    if (!autoScrollEnabled.value) {
      return
    }
    await nextTick()
    scrollToBottom()
  },
  { flush: 'post' },
)

onMounted(async () => {
  await nextTick()
  scrollToBottom()
})
</script>

<template>
  <div ref="containerRef" class="chat-log" @scroll="handleScroll">
    <div v-for="message in messages" :key="message.id" class="message-row" :class="`message-row--${message.role}`">
      <div class="message" :class="`message--${message.role}`">
        <div class="message__header">
          <div class="message__role"
            :title="message.role === 'user' ? (userTitle || userLabel || '用户') : (assistantTitle || assistantLabel)">
            {{ message.role === 'user' ? (userLabel || '用户') : assistantLabel }}
          </div>
          <div class="message__time">{{ formatMessageTime(message.createdAt) }}</div>
        </div>
        <div v-if="parseTaskStructuredMessage(message.content)?.kind === 'plan'"
          class="message__task-card message__task-card--plan">
          <div class="message__task-card-title">{{ parseTaskStructuredMessage(message.content)?.title }}</div>
          <pre class="message__code"><code>{{ parseTaskStructuredMessage(message.content)?.body }}</code></pre>
        </div>
        <div v-else-if="parseTaskStructuredMessage(message.content)?.kind === 'step-start'"
          class="message__task-card message__task-card--step">
          <div class="message__task-card-title">{{ parseTaskStructuredMessage(message.content)?.stepLabel }}</div>
          <div class="message__task-card-subtitle">{{ parseTaskStructuredMessage(message.content)?.title }}</div>
          <pre class="message__code"><code>{{ parseTaskStructuredMessage(message.content)?.command }}</code></pre>
        </div>
        <div v-else-if="parseTaskStructuredMessage(message.content)?.kind === 'step-result'"
          class="message__task-card message__task-card--result">
          <div class="message__task-card-title">{{ parseTaskStructuredMessage(message.content)?.stepLabel }}</div>
          <MarkdownContent class="message__content"
            :content="parseTaskStructuredMessage(message.content)?.body || ''" />
        </div>
        <div v-else-if="parseTaskStructuredMessage(message.content)?.kind === 'summary'"
          class="message__task-card message__task-card--summary">
          <div class="message__task-card-title">{{ parseTaskStructuredMessage(message.content)?.title }}</div>
          <MarkdownContent class="message__content"
            :content="parseTaskStructuredMessage(message.content)?.body || ''" />
        </div>
        <div v-else-if="parseTaskStructuredMessage(message.content)?.kind === 'repair'"
          class="message__task-card message__task-card--repair">
          <div class="message__task-card-title">{{ parseTaskStructuredMessage(message.content)?.title }}</div>
          <MarkdownContent class="message__content"
            :content="parseTaskStructuredMessage(message.content)?.body || ''" />
        </div>
        <div v-else-if="parseTaskStructuredMessage(message.content)?.kind === 'info'"
          class="message__task-card message__task-card--info">
          <div class="message__task-card-title">{{ parseTaskStructuredMessage(message.content)?.title }}</div>
          <MarkdownContent class="message__content"
            :content="parseTaskStructuredMessage(message.content)?.body || ''" />
        </div>
        <div v-else-if="isTaskPlanMessage(message)" class="message__content">
          <MarkdownContent :content="getTaskPlanIntro(message.content)" />
          <pre v-if="getTaskPlanCode(message.content)"
            class="message__code"><code>{{ getTaskPlanCode(message.content) }}</code></pre>
        </div>
        <MarkdownContent v-else class="message__content" :content="message.content" />
        <div v-if="canShowTaskApproval(message)" class="message__task-approval">
          <p class="message__task-approval-hint">{{ taskApprovalHint || '该任务需要人工确认后才会继续执行。' }}</p>
          <div class="message__task-approval-actions">
            <el-button type="primary" :loading="taskApprovalLoading" @click="emit('taskConfirm', true)">批准执行</el-button>
            <el-button :disabled="taskApprovalLoading" @click="emit('taskConfirm', false)">拒绝</el-button>
          </div>
        </div>
        <div v-if="canShowActions(message)" class="message__actions">
          <el-button text circle :icon="CopyDocument" title="复制" @click="emit('copy', message.id)" />
          <el-button v-if="canRetry(message)" text circle :icon="RefreshRight" title="重答"
            @click="emit('retry', message.id)" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-log {
  display: grid;
  gap: 18px;
  height: 100%;
  min-height: 0;
  overflow: auto;
  align-content: start;
  padding-right: 6px;
}

.message-row {
  display: flex;
  align-items: flex-start;
}

.message-row--user {
  justify-content: flex-end;
}

.message-row--user .message {
  max-width: min(84%, 920px);
}

.message-row--assistant .message {
  max-width: min(92%, 1040px);
}

.message {
  width: fit-content;
  padding: 18px 20px;
  border-radius: 22px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(12px);
}

.message__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.message--user {
  background: linear-gradient(135deg, rgba(0, 113, 227, 0.3), rgba(88, 86, 214, 0.24));
}

.message--assistant {
  background: rgba(255, 255, 255, 0.04);
}

.message__role {
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.65);
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.message__time {
  margin-bottom: 8px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.42);
  white-space: nowrap;
}

.message__content {
  white-space: pre-wrap;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.message__task-card {
  display: grid;
  gap: 10px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.message__task-card--plan {
  background: rgba(30, 64, 175, 0.18);
}

.message__task-card--step {
  background: rgba(8, 47, 73, 0.28);
}

.message__task-card--result {
  background: rgba(6, 78, 59, 0.22);
}

.message__task-card--summary {
  background: rgba(88, 28, 135, 0.22);
}

.message__task-card--repair {
  background: rgba(120, 53, 15, 0.24);
}

.message__task-card--info {
  background: rgba(55, 65, 81, 0.26);
}

.message__task-card-title {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: rgba(191, 219, 254, 0.88);
  text-transform: uppercase;
}

.message__task-card-subtitle {
  font-size: 15px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.95);
}

.message__code {
  margin: 12px 0 0;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.08);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-family: Consolas, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
}

.message__actions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
  margin-top: 10px;
}

.message__task-approval {
  display: grid;
  gap: 10px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.message__task-approval-hint {
  margin: 0;
  color: #f59e0b;
}

.message__task-approval-actions {
  display: flex;
  gap: 12px;
}

@media (max-width: 720px) {

  .message-row--user .message,
  .message-row--assistant .message {
    max-width: 100%;
    width: 100%;
  }

  .message__header {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }

  .message__task-approval-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
