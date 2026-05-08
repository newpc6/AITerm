<script setup lang="ts">
import { Promotion, VideoPause } from '@element-plus/icons-vue'

const modelValue = defineModel<string>({ required: true })

defineProps<{
  streaming: boolean
  disabled: boolean
  placeholder: string
}>()

const emit = defineEmits<{
  submit: []
  stop: []
}>()

function handleSubmit() {
  emit('submit')
}

function handleStop() {
  emit('stop')
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
      <el-input v-model="modelValue" type="textarea" :rows="3" resize="none" :placeholder="placeholder"
        :disabled="disabled" @keydown="handleKeydown" />
      <el-button v-if="streaming" class="chat-input__btn" type="danger" :icon="VideoPause" circle @click="handleStop" />
      <el-button v-else class="chat-input__btn" type="primary" :icon="Promotion" circle
        :disabled="disabled || !modelValue.trim()" @click="handleSubmit" />
    </div>
  </div>
</template>

<style scoped>
.chat-input {
  flex-shrink: 0;
}

.chat-input__wrapper {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.chat-input__btn {
  flex-shrink: 0;
  background-color: transparent;
  border-color: white;
  width: 32px;
  height: 32px;
  margin-top: 8px;
}

.chat-input__btn:hover {
  background: var(--color-bg-card-hover);
  border-color: rgba(255, 255, 255, 0.12);
}

:deep(.el-textarea__inner) {
  min-height: 92px !important;
}
</style>
