<script setup lang="ts">
import type { ConversationMode, NodeItem } from '@/types/api'

const modelValue = defineModel<string>({ required: true })

defineProps<{
  activeMode: ConversationMode
  chatStreaming: boolean
  conversationLabel: string
  activeTaskId: string
  availableNodes: NodeItem[]
  loading: boolean
  selectedNodeId: string
  streaming: boolean
}>()

const emit = defineEmits<{
  submit: []
  stopChat: []
}>()

function handleSubmit() {
  emit("submit")
}

function handleStopChat() {
  emit('stopChat')
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.ctrlKey && !event.metaKey) {
    event.preventDefault()
    handleSubmit()
  }
}
</script>

<template>
  <div class="chat-input">
    <el-input v-model="modelValue" type="textarea" :rows="3" resize="none"
      :placeholder="activeMode === 'task' ? '描述你希望 AITerm 自动执行的任务（回车发送，Ctrl+回车换行）' : '输入你想和模型继续讨论的问题（回车发送，Ctrl+回车换行）'"
      @keydown="handleKeydown" />
    <div class="chat-actions">
      <div class="label">
        模式: {{ activeMode === 'task' ? '任务' : '对话' }}
        <span> | 会话: {{ conversationLabel }}</span>
        <span v-if="activeTaskId"> | 任务: {{ activeTaskId }}</span>
        <span v-if="streaming"> | 执行中</span>
      </div>
      <div class="chat-actions__buttons">
        <el-button v-if="chatStreaming" @click="handleStopChat">中止回答</el-button>
        <el-button type="primary" :loading="loading" @click="handleSubmit">{{ activeMode === 'task' ? '创建任务' : '发送对话'
          }}</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-actions__buttons {
  display: flex;
  gap: 12px;
}

:deep(.el-textarea__inner) {
  min-height: 92px !important;
}

@media (max-width: 720px) {
  .chat-actions__buttons {
    width: 100%;
    justify-content: stretch;
  }
}
</style>
