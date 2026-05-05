<script setup lang="ts">
import { computed } from 'vue'
import { CopyDocument, RefreshRight } from '@element-plus/icons-vue'
import type { ChatMessage } from '@/types/chat'

const props = defineProps<{
  message: ChatMessage
  userLabel?: string
  userTitle?: string
  assistantLabel: string
  assistantTitle?: string
  actionableMessageIds?: string[]
  retryableMessageIds?: string[]
  streamingMessageId?: string
}>()

const emit = defineEmits<{
  copy: [messageId: string]
  retry: [messageId: string]
}>()

const actionableMessageIdSet = computed(() => new Set(props.actionableMessageIds ?? []))
const retryableMessageIdSet = computed(() => new Set(props.retryableMessageIds ?? []))

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

function isStreaming(message: ChatMessage) {
  return props.streamingMessageId === message.id
}
</script>

<template>
  <div class="message-row" :class="`message-row--${message.role}`">
    <div class="message" :class="`message--${message.role}`">
      <div class="message__header">
        <div class="message__role"
          :title="message.role === 'user' ? (userTitle || userLabel || '用户') : (assistantTitle || assistantLabel)">
          {{ message.role === 'user' ? (userLabel || '用户') : assistantLabel }}
        </div>
        <div class="message__time">{{ formatMessageTime(message.createdAt) }}</div>
      </div>
      <slot :isStreaming="isStreaming(message)"></slot>
      <div v-if="canShowActions(message)" class="message__actions">
        <el-button text circle :icon="CopyDocument" title="复制" @click="emit('copy', message.id)" />
        <el-button v-if="canRetry(message)" text circle :icon="RefreshRight" title="重答"
          @click="emit('retry', message.id)" />
      </div>
    </div>
  </div>
</template>

<style scoped>
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
  width: 85%;
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

.message__actions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
}
</style>
