<script setup lang="ts">
import { Promotion, VideoPause } from '@element-plus/icons-vue'

const modelValue = defineModel<string>({ required: true })

defineProps<{
  chatStreaming: boolean
  loading: boolean
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
    <div class="chat-input__wrapper">
      <el-input v-model="modelValue" type="textarea" :rows="3" resize="none" placeholder="输入你的问题或任务描述（回车发送，Ctrl+回车换行）"
        @keydown="handleKeydown" />
      <el-button v-if="chatStreaming" class="chat-input__send-btn" type="danger" :icon="VideoPause" circle
        @click="handleStopChat" />
      <el-button v-else class="chat-input__send-btn" type="primary" :icon="Promotion" circle
        :disabled="loading || !modelValue.trim()" @click="handleSubmit" />
    </div>
  </div>
</template>

<style scoped>
.chat-input__wrapper {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.chat-input__send-btn {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  margin-top: 8px;
  background: var(--color-bg-input);
  border: 1px solid var(--color-border-primary);
}

.chat-input__send-btn:hover {
  background: var(--color-bg-card-hover);
  border-color: rgba(255, 255, 255, 0.12);
}

:deep(.el-textarea__inner) {
  min-height: 92px !important;
}
</style>
