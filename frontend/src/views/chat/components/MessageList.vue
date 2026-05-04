<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import {
  MessageItem,
  MessageContent,
  MessageLoading,
  ExecutePlanCard,
  ExecuteStepCard,
  ExecuteInputCard,
  ExecuteApprovalCard,
  ExecuteApprovedCard,
  ExecuteInfoCard,
} from './messages'
import {
  getMessageKind,
  parseUserInputResponse,
  parseStructuredInputResponse,
  isExecutePlanMessage,
  getExecutePlanIntro,
  getExecutePlanCode,
  isInputRequestMessage,
} from './useMessageParser'
import type { ChatMessage } from '@/types/chat'

const props = defineProps<{
  actionableMessageIds?: string[]
  assistantLabel: string
  assistantTitle?: string
  messages: ChatMessage[]
  retryableMessageIds?: string[]
  executeApprovalHint?: string
  executeApprovalLoading?: boolean
  executeApprovalMessageId?: string
  userLabel?: string
  userTitle?: string
  streamingMessageId?: string
  isReasoningActive?: boolean
  analyzing?: boolean
  canStopExecute?: boolean
  executeInputRequest?: {
    question: string
    input_type: 'text' | 'select' | 'multiselect'
    options?: string[]
    placeholder?: string
  }
  executeInputMessageId?: string
  executeInputLoading?: boolean
  executeUserInput?: string
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

const emit = defineEmits<{
  copy: [messageId: string]
  retry: [messageId: string]
  executeConfirm: [approved: boolean]
  stopExecute: []
  submitExecuteInput: [value: string]
}>()

const containerRef = ref<HTMLDivElement | null>(null)
const autoScrollEnabled = ref(true)
const scrollThreshold = 32

const actionableMessageIdSet = computed(() => new Set(props.actionableMessageIds ?? []))
const retryableMessageIdSet = computed(() => new Set(props.retryableMessageIds ?? []))
const messageSignature = computed(() =>
  [
    props.messages.map((message) => {
      const metaStr = message.metadata ? JSON.stringify(message.metadata) : ''
      return `${message.id}:${message.role}:${message.content}:${metaStr}:${message.createdAt}`
    }).join('\n<aiterm-message>\n'),
    Array.from(actionableMessageIdSet.value).join(','),
    Array.from(retryableMessageIdSet.value).join(','),
    props.streamingMessageId,
    props.isReasoningActive ? 'reasoning' : '',
    props.executeInputRequest?.question,
  ].join('\n<aiterm-state>\n'),
)

function canShowExecuteApproval(message: ChatMessage) {
  return message.role === 'assistant' && !!message.content && props.executeApprovalMessageId === message.id
}

function isStreaming(message: ChatMessage) {
  return props.streamingMessageId === message.id
}

function checkInputRequestMessage(message: ChatMessage) {
  return isInputRequestMessage(message, props.executeInputRequest, props.executeUserInput)
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

function handleStopExecute() {
  emit('stopExecute')
}

function handleSubmitInput(value: string) {
  emit('submitExecuteInput', value)
}

function handleExecuteConfirm(approved: boolean) {
  emit('executeConfirm', approved)
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
    <MessageItem v-for="message in messages" :key="message.id" :message="message" :user-label="userLabel"
      :user-title="userTitle" :assistant-label="assistantLabel" :assistant-title="assistantTitle"
      :actionable-message-ids="actionableMessageIds" :retryable-message-ids="retryableMessageIds"
      :streaming-message-id="streamingMessageId" @copy="emit('copy', $event)" @retry="emit('retry', $event)">
      <template #default="{ isStreaming: isMsgStreaming }">
        <MessageLoading v-if="isMsgStreaming && !message.content.trim()" />
        <template v-else>
          <ExecuteInputCard v-if="checkInputRequestMessage(message)" :question="executeInputRequest?.question"
            :input-type="executeInputRequest?.input_type" :options="executeInputRequest?.options"
            :placeholder="executeInputRequest?.placeholder" :loading="executeInputLoading"
            @submit="handleSubmitInput" />
          <ExecuteInputCard v-else-if="parseStructuredInputResponse(message.content)" answered
            :question="parseStructuredInputResponse(message.content)?.question"
            :input-type="parseStructuredInputResponse(message.content)?.inputType"
            :options="parseStructuredInputResponse(message.content)?.options"
            :answer="parseStructuredInputResponse(message.content)?.answer" />
          <ExecuteInputCard v-else-if="parseUserInputResponse(message.content)" answered
            :answer="parseUserInputResponse(message.content)?.answer" />
          <ExecuteInfoCard v-else-if="getMessageKind(message)?.kind === 'analyzing'" kind="info"
            :title="getMessageKind(message)?.title" :body="getMessageKind(message)?.body"
            :is-streaming="isMsgStreaming" />
          <ExecutePlanCard v-else-if="getMessageKind(message)?.kind === 'plan'" :title="getMessageKind(message)?.title"
            :body="getMessageKind(message)?.body" />
          <ExecuteStepCard v-else-if="getMessageKind(message)?.kind === 'step-start'"
            :step-label="getMessageKind(message)?.stepLabel" :title="getMessageKind(message)?.title"
            :command="getMessageKind(message)?.command" :body="getMessageKind(message)?.body"
            :output="getMessageKind(message)?.output" :status="getMessageKind(message)?.status"
            :is-streaming="isMsgStreaming" :can-stop-execute="canStopExecute" @stop-execute="handleStopExecute" />
          <ExecuteInfoCard v-else-if="getMessageKind(message)?.kind === 'step-result'" kind="result"
            :title="getMessageKind(message)?.stepLabel" :body="getMessageKind(message)?.body" />
          <ExecuteInfoCard v-else-if="getMessageKind(message)?.kind === 'summary'" kind="summary"
            :title="getMessageKind(message)?.title" :body="getMessageKind(message)?.body" />
          <ExecuteInfoCard v-else-if="getMessageKind(message)?.kind === 'repair'" kind="repair"
            :title="getMessageKind(message)?.title" :body="getMessageKind(message)?.body" />
          <ExecuteInfoCard v-else-if="getMessageKind(message)?.kind === 'info'" kind="info"
            :title="getMessageKind(message)?.title" :body="getMessageKind(message)?.body" />
          <ExecuteApprovedCard v-else-if="getMessageKind(message)?.kind === 'approved'"
            :title="getMessageKind(message)?.title" :body="getMessageKind(message)?.body" />
          <div v-else-if="isExecutePlanMessage(message)" class="message__content">
            <span>{{ getExecutePlanIntro(message.content) }}</span>
            <pre v-if="getExecutePlanCode(message.content)"
              class="message__code"><code>{{ getExecutePlanCode(message.content) }}</code></pre>
          </div>
          <MessageContent v-else-if="message.type !== 'approval'" :content="message.content" :role="message.role"
            :is-streaming="isMsgStreaming" :is-reasoning-active="isMsgStreaming && isReasoningActive"
            :metadata="message.metadata" :display-settings="displaySettings" />
        </template>

        <ExecuteApprovalCard v-if="canShowExecuteApproval(message)" :hint="message.content"
          :loading="executeApprovalLoading" @confirm="handleExecuteConfirm" />
      </template>
    </MessageItem>
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

.message__content {
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.message__code {
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
