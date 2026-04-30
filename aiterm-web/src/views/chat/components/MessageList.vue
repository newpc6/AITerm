<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { CopyDocument, RefreshRight, Loading, VideoPause } from '@element-plus/icons-vue'

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
  streamingMessageId?: string
  analyzing?: boolean
  canStopTask?: boolean
  taskInputRequest?: {
    question: string
    input_type: 'text' | 'select' | 'multiselect'
    options?: string[]
    placeholder?: string
  }
  taskInputMessageId?: string
  taskInputLoading?: boolean
  taskUserInput?: string
}>()

const emit = defineEmits<{
  copy: [messageId: string]
  retry: [messageId: string]
  taskConfirm: [approved: boolean]
  stopTask: []
  submitTaskInput: [value: string]
}>()

const containerRef = ref<HTMLDivElement | null>(null)
const autoScrollEnabled = ref(true)
const scrollThreshold = 32
const userInputValue = ref('')
const selectedOptions = ref<string[]>([])
const otherInputValue = ref('')
const OTHER_OPTION = '__other__'

const actionableMessageIdSet = computed(() => new Set(props.actionableMessageIds ?? []))
const retryableMessageIdSet = computed(() => new Set(props.retryableMessageIds ?? []))
const messageSignature = computed(() =>
  [
    props.messages.map((message) => `${message.id}:${message.role}:${message.content}:${message.createdAt}`).join('\n<aiterm-message>\n'),
    Array.from(actionableMessageIdSet.value).join(','),
    Array.from(retryableMessageIdSet.value).join(','),
    props.streamingMessageId,
    props.taskInputRequest?.question,
  ].join('\n<aiterm-state>\n'),
)

watch(
  () => props.taskInputRequest,
  (newVal) => {
    if (newVal) {
      userInputValue.value = ''
      selectedOptions.value = []
      otherInputValue.value = ''
    }
  },
  { immediate: true },
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

function isStreaming(message: ChatMessage) {
  return props.streamingMessageId === message.id
}

function isTaskPlanMessage(message: ChatMessage) {
  return message.role === 'assistant' && message.content.includes('任务计划如下') && message.content.includes('\n')
}

type TaskStructuredMessage = {
  kind: 'plan' | 'step-start' | 'step-result' | 'summary' | 'repair' | 'info' | 'analyzing' | 'input-request'
  title?: string
  stepLabel?: string
  body?: string
  command?: string
  question?: string
  options?: string[]
}

type UserInputResponse = {
  question: string
  answer: string
}

function parseUserInputResponse(content: string): UserInputResponse | null {
  const normalized = content.trim()
  if (!normalized) {
    return null
  }

  const match = normalized.match(/^用户输入[:：]\s*(.+)$/)
  if (match) {
    return {
      question: '',
      answer: match[1].trim(),
    }
  }

  return null
}

function parseTaskStructuredMessage(content: string): TaskStructuredMessage | null {
  const normalized = content.trim()
  if (!normalized) {
    return null
  }

  if (normalized.includes('正在') && normalized.includes('分析任务')) {
    return {
      kind: 'analyzing',
      title: '分析中',
      body: normalized,
    }
  }

  if (normalized.includes('正在') && normalized.includes('执行')) {
    return {
      kind: 'step-start',
      title: '执行中',
      body: normalized,
    }
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

function handleStopTask() {
  emit('stopTask')
}

function handleSubmitInput() {
  let value = ''
  if (props.taskInputRequest?.input_type === 'multiselect') {
    const actualOptions = selectedOptions.value.filter(opt => opt !== OTHER_OPTION)
    if (selectedOptions.value.includes(OTHER_OPTION) && otherInputValue.value.trim()) {
      actualOptions.push(otherInputValue.value.trim())
    }
    value = actualOptions.join(', ')
  } else if (props.taskInputRequest?.input_type === 'select') {
    if (userInputValue.value === OTHER_OPTION) {
      value = otherInputValue.value.trim()
    } else {
      value = userInputValue.value
    }
  } else {
    value = userInputValue.value
  }

  if (!value.trim()) {
    return
  }

  emit('submitTaskInput', value)
}

function handleSelectOption(option: string) {
  userInputValue.value = option
}

function toggleMultiOption(option: string) {
  const index = selectedOptions.value.indexOf(option)
  if (index >= 0) {
    selectedOptions.value.splice(index, 1)
  } else {
    selectedOptions.value.push(option)
  }
}

function isOptionSelected(option: string) {
  return selectedOptions.value.includes(option)
}

function isOtherSelected() {
  return userInputValue.value === OTHER_OPTION
}

function isOtherSelectedInMulti() {
  return selectedOptions.value.includes(OTHER_OPTION)
}

function getDisplayOptions(options?: string[]) {
  if (!options) return []
  return [...options, OTHER_OPTION]
}

function isOptionInAnswer(option: string, answer: string, inputType?: string) {
  if (!answer) return false
  if (inputType === 'select') {
    return answer.trim() === option.trim()
  }
  const selectedItems = answer.split(',').map(s => s.trim()).filter(Boolean)
  return selectedItems.includes(option.trim())
}

type StructuredInputRequest = {
  question: string
  inputType: string
  options: string[]
  placeholder: string
}

type StructuredInputResponse = {
  question: string
  inputType: string
  options: string[]
  answer: string
}

function parseStructuredInputRequest(content: string): StructuredInputRequest | null {
  if (content.startsWith('[INPUT_REQUEST]') && content.includes('[/INPUT_REQUEST]')) {
    const questionMatch = content.match(/问题: (.+)/)
    const typeMatch = content.match(/类型: (.+)/)
    const optionsMatch = content.match(/选项: (.+)/)
    const placeholderMatch = content.match(/占位符: (.+)/)

    const optionsStr = optionsMatch?.[1] || ''
    const options = optionsStr ? optionsStr.split('|||').filter(Boolean) : []

    return {
      question: questionMatch?.[1] || '',
      inputType: typeMatch?.[1] || 'text',
      options,
      placeholder: placeholderMatch?.[1] || '',
    }
  }

  if (content.includes('需要您的输入') || content.includes('需要人工确认')) {
    const lines = content.split('\n')
    let question = ''
    let options: string[] = []

    for (const line of lines) {
      const questionMatch = line.match(/[:：]\s*(.+)$/)
      if (questionMatch && !line.includes('选项')) {
        question = questionMatch[1].trim()
      }
      const optionsMatch = line.match(/选项[:：]\s*(.+)$/)
      if (optionsMatch) {
        const optionsText = optionsMatch[1].trim()
        options = optionsText.split(/,\s+/).map(s => s.trim()).filter(Boolean)
      }
    }

    return {
      question: question || content,
      inputType: options.length > 0 ? 'select' : 'text',
      options,
      placeholder: '',
    }
  }

  return null
}

function parseStructuredInputResponse(content: string): StructuredInputResponse | null {
  if (!content.startsWith('[INPUT_RESPONSE]') || !content.includes('[/INPUT_RESPONSE]')) {
    return null
  }

  const questionMatch = content.match(/问题: (.+)/)
  const typeMatch = content.match(/类型: (.+)/)
  const optionsMatch = content.match(/选项: (.+)/)
  const answerMatch = content.match(/回答: (.+)/)

  const optionsStr = optionsMatch?.[1] || ''
  const options = optionsStr ? optionsStr.split('|||').filter(Boolean) : []

  return {
    question: questionMatch?.[1] || '',
    inputType: typeMatch?.[1] || 'text',
    options,
    answer: answerMatch?.[1] || '',
  }
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
        <div v-if="isStreaming(message) && !message.content.trim()" class="message__loading">
          <el-icon class="message__loading-icon is-loading">
            <Loading />
          </el-icon>
          <span class="message__loading-text">思考中...</span>
        </div>
        <template v-else>
          <div
            v-if="taskInputRequest && (message.content === '等待用户输入...' || message.content.startsWith('[INPUT_REQUEST]')) && !taskUserInput"
            class="message__task-card message__task-card--input">
            <div class="message__task-card-header">
              <div class="message__task-card-title">需要输入</div>
              <el-icon v-if="isStreaming(message)" class="message__task-card-loading is-loading">
                <Loading />
              </el-icon>
            </div>
            <div v-if="taskInputRequest.question" class="message__input-question">{{ taskInputRequest.question }}</div>
            <div v-if="taskInputRequest.input_type === 'text'" class="message__input-form-inline">
              <div class="message__input-row">
                <el-input v-model="userInputValue" :placeholder="taskInputRequest.placeholder || '请输入...'"
                  :disabled="taskInputLoading" class="message__input-field" @keyup.enter="handleSubmitInput" />
                <el-button type="primary" :loading="taskInputLoading" :disabled="!userInputValue.trim()"
                  @click="handleSubmitInput">提交</el-button>
              </div>
            </div>
            <div v-else-if="taskInputRequest.input_type === 'select'" class="message__input-form-inline">
              <div class="message__input-options-form">
                <div v-for="option in getDisplayOptions(taskInputRequest.options)" :key="option"
                  class="message__input-option-item" :class="{ 'is-selected': userInputValue === option }"
                  @click="handleSelectOption(option)">
                  <span class="message__input-option-radio">
                    <span v-if="userInputValue === option" class="message__input-option-radio-inner"></span>
                  </span>
                  <span class="message__input-option-text">{{ option === OTHER_OPTION ? '其他' : option }}</span>
                </div>
              </div>
              <div v-if="isOtherSelected()" class="message__input-row message__input-row--options">
                <el-input v-model="otherInputValue" placeholder="请输入自定义内容" :disabled="taskInputLoading"
                  class="message__input-field" @keyup.enter="handleSubmitInput" />
                <el-button type="primary" :loading="taskInputLoading" :disabled="!otherInputValue.trim()"
                  @click="handleSubmitInput">提交</el-button>
              </div>
              <div v-else class="message__input-row message__input-row--options">
                <el-button type="primary" :loading="taskInputLoading" :disabled="!userInputValue"
                  @click="handleSubmitInput">提交</el-button>
              </div>
            </div>
            <div v-else-if="taskInputRequest.input_type === 'multiselect'" class="message__input-form-inline">
              <div class="message__input-options-form">
                <div v-for="option in getDisplayOptions(taskInputRequest.options)" :key="option"
                  class="message__input-option-item" :class="{ 'is-selected': isOptionSelected(option) }"
                  @click="toggleMultiOption(option)">
                  <span class="message__input-option-checkbox">
                    <span v-if="isOptionSelected(option)" class="message__input-option-checkbox-inner">✓</span>
                  </span>
                  <span class="message__input-option-text">{{ option === OTHER_OPTION ? '其他' : option }}</span>
                </div>
              </div>
              <div v-if="isOtherSelectedInMulti()" class="message__input-row message__input-row--options">
                <el-input v-model="otherInputValue" placeholder="请输入自定义内容" :disabled="taskInputLoading"
                  class="message__input-field" @keyup.enter="handleSubmitInput" />
              </div>
              <div class="message__input-row message__input-row--options">
                <el-button type="primary" :loading="taskInputLoading"
                  :disabled="selectedOptions.length === 0 || (isOtherSelectedInMulti() && !otherInputValue.trim())"
                  @click="handleSubmitInput">提交选择</el-button>
              </div>
            </div>
          </div>
          <div v-else-if="taskUserInput && message.content.startsWith('[INPUT_RESPONSE]')"
            class="message__task-card message__task-card--input message__task-card--answered">
            <div class="message__task-card-header">
              <div class="message__task-card-title">已输入</div>
            </div>
            <div class="message__input-question">{{ parseStructuredInputResponse(message.content)?.question }}</div>
            <div v-if="parseStructuredInputResponse(message.content)?.options?.length"
              class="message__input-options-readonly">
              <div class="message__input-options-label">选项：</div>
              <div class="message__input-options-readonly-list">
                <div v-for="option in parseStructuredInputResponse(message.content)?.options" :key="option"
                  class="message__input-option-readonly-item"
                  :class="{ 'is-selected': isOptionInAnswer(option, parseStructuredInputResponse(message.content)?.answer || '', parseStructuredInputResponse(message.content)?.inputType) }">
                  <span v-if="parseStructuredInputResponse(message.content)?.inputType === 'select'"
                    class="message__input-option-radio">
                    <span
                      v-if="isOptionInAnswer(option, parseStructuredInputResponse(message.content)?.answer || '', parseStructuredInputResponse(message.content)?.inputType)"
                      class="message__input-option-radio-inner"></span>
                  </span>
                  <span v-else class="message__input-option-checkbox">
                    <span
                      v-if="isOptionInAnswer(option, parseStructuredInputResponse(message.content)?.answer || '', parseStructuredInputResponse(message.content)?.inputType)"
                      class="message__input-option-checkbox-inner">✓</span>
                  </span>
                  <span class="message__input-option-text">{{ option }}</span>
                </div>
              </div>
            </div>
            <div class="message__input-answer">
              <span class="message__input-answer-label">您的回答：</span>
              <span class="message__input-answer-value">{{ parseStructuredInputResponse(message.content)?.answer
              }}</span>
            </div>
          </div>
          <div v-else-if="parseStructuredInputRequest(message.content) && taskUserInput"
            class="message__task-card message__task-card--input message__task-card--answered">
            <div class="message__task-card-header">
              <div class="message__task-card-title">已输入</div>
            </div>
            <div class="message__input-question">{{ parseStructuredInputRequest(message.content)?.question }}</div>
            <div v-if="parseStructuredInputRequest(message.content)?.options?.length"
              class="message__input-options-readonly">
              <div class="message__input-options-label">选项：</div>
              <div class="message__input-options-readonly-list">
                <div v-for="option in parseStructuredInputRequest(message.content)?.options" :key="option"
                  class="message__input-option-readonly-item"
                  :class="{ 'is-selected': isOptionInAnswer(option, taskUserInput, parseStructuredInputRequest(message.content)?.inputType) }">
                  <span v-if="parseStructuredInputRequest(message.content)?.inputType === 'select'"
                    class="message__input-option-radio">
                    <span
                      v-if="isOptionInAnswer(option, taskUserInput, parseStructuredInputRequest(message.content)?.inputType)"
                      class="message__input-option-radio-inner"></span>
                  </span>
                  <span v-else class="message__input-option-checkbox">
                    <span
                      v-if="isOptionInAnswer(option, taskUserInput, parseStructuredInputRequest(message.content)?.inputType)"
                      class="message__input-option-checkbox-inner">✓</span>
                  </span>
                  <span class="message__input-option-text">{{ option }}</span>
                </div>
              </div>
            </div>
            <div class="message__input-answer">
              <span class="message__input-answer-label">您的回答：</span>
              <span class="message__input-answer-value">{{ taskUserInput }}</span>
            </div>
          </div>
          <div v-else-if="parseStructuredInputRequest(message.content)"
            class="message__task-card message__task-card--input">
            <div class="message__task-card-header">
              <div class="message__task-card-title">需要输入</div>
            </div>
            <div class="message__input-question">{{ parseStructuredInputRequest(message.content)?.question }}</div>
            <div v-if="parseStructuredInputRequest(message.content)?.options?.length"
              class="message__input-options-readonly">
              <div class="message__input-options-label">选项：</div>
              <div class="message__input-options-readonly-list">
                <div v-for="option in parseStructuredInputRequest(message.content)?.options" :key="option"
                  class="message__input-option-readonly-item">
                  <span v-if="parseStructuredInputRequest(message.content)?.inputType === 'select'"
                    class="message__input-option-radio">
                  </span>
                  <span v-else class="message__input-option-checkbox">
                  </span>
                  <span class="message__input-option-text">{{ option }}</span>
                </div>
              </div>
            </div>
          </div>
          <div v-else-if="parseStructuredInputResponse(message.content)"
            class="message__task-card message__task-card--input message__task-card--answered">
            <div class="message__task-card-header">
              <div class="message__task-card-title">已输入</div>
            </div>
            <div class="message__input-question">{{ parseStructuredInputResponse(message.content)?.question }}</div>
            <div v-if="parseStructuredInputResponse(message.content)?.options?.length"
              class="message__input-options-readonly">
              <div class="message__input-options-label">选项：</div>
              <div class="message__input-options-readonly-list">
                <div v-for="option in parseStructuredInputResponse(message.content)?.options" :key="option"
                  class="message__input-option-readonly-item"
                  :class="{ 'is-selected': isOptionInAnswer(option, parseStructuredInputResponse(message.content)?.answer || '', parseStructuredInputResponse(message.content)?.inputType) }">
                  <span v-if="parseStructuredInputResponse(message.content)?.inputType === 'select'"
                    class="message__input-option-radio">
                    <span
                      v-if="isOptionInAnswer(option, parseStructuredInputResponse(message.content)?.answer || '', parseStructuredInputResponse(message.content)?.inputType)"
                      class="message__input-option-radio-inner"></span>
                  </span>
                  <span v-else class="message__input-option-checkbox">
                    <span
                      v-if="isOptionInAnswer(option, parseStructuredInputResponse(message.content)?.answer || '', parseStructuredInputResponse(message.content)?.inputType)"
                      class="message__input-option-checkbox-inner">✓</span>
                  </span>
                  <span class="message__input-option-text">{{ option }}</span>
                </div>
              </div>
            </div>
            <div class="message__input-answer">
              <span class="message__input-answer-label">您的回答：</span>
              <span class="message__input-answer-value">{{ parseStructuredInputResponse(message.content)?.answer
                }}</span>
            </div>
          </div>
          <div v-else-if="parseUserInputResponse(message.content)"
            class="message__task-card message__task-card--input message__task-card--answered">
            <div class="message__task-card-header">
              <div class="message__task-card-title">已输入</div>
            </div>
            <div class="message__input-question">{{ parseUserInputResponse(message.content)?.question }}</div>
            <div class="message__input-answer">
              <span class="message__input-answer-label">您的回答：</span>
              <span class="message__input-answer-value">{{ parseUserInputResponse(message.content)?.answer }}</span>
            </div>
          </div>
          <div v-else-if="parseTaskStructuredMessage(message.content)?.kind === 'analyzing'"
            class="message__task-card message__task-card--analyzing">
            <div class="message__task-card-header">
              <div class="message__task-card-title">{{ parseTaskStructuredMessage(message.content)?.title }}</div>
              <el-icon v-if="isStreaming(message)" class="message__task-card-loading is-loading">
                <Loading />
              </el-icon>
            </div>
            <MarkdownContent class="message__content" mode="markdown"
              :content="parseTaskStructuredMessage(message.content)?.body || ''" />
          </div>
          <div v-else-if="parseTaskStructuredMessage(message.content)?.kind === 'plan'"
            class="message__task-card message__task-card--plan">
            <div class="message__task-card-title">{{ parseTaskStructuredMessage(message.content)?.title }}</div>
            <pre class="message__code"><code>{{ parseTaskStructuredMessage(message.content)?.body }}</code></pre>
          </div>
          <div v-else-if="parseTaskStructuredMessage(message.content)?.kind === 'step-start'"
            class="message__task-card message__task-card--step">
            <div class="message__task-card-header">
              <div class="message__task-card-title">{{ parseTaskStructuredMessage(message.content)?.stepLabel ||
                parseTaskStructuredMessage(message.content)?.title }}</div>
              <div class="message__task-card-actions">
                <el-icon v-if="isStreaming(message)" class="message__task-card-loading is-loading">
                  <Loading />
                </el-icon>
                <el-button v-if="isStreaming(message) && canStopTask" type="danger" size="small" :icon="VideoPause"
                  @click="handleStopTask">
                  停止
                </el-button>
              </div>
            </div>
            <div
              v-if="parseTaskStructuredMessage(message.content)?.title && parseTaskStructuredMessage(message.content)?.stepLabel"
              class="message__task-card-subtitle">{{ parseTaskStructuredMessage(message.content)?.title }}</div>
            <pre v-if="parseTaskStructuredMessage(message.content)?.command" class="message__code"><code>{{
              parseTaskStructuredMessage(message.content)?.command }}</code></pre>
            <MarkdownContent v-else class="message__content" mode="markdown"
              :content="parseTaskStructuredMessage(message.content)?.body || ''" />
          </div>
          <div v-else-if="parseTaskStructuredMessage(message.content)?.kind === 'step-result'"
            class="message__task-card message__task-card--result">
            <div class="message__task-card-title">{{ parseTaskStructuredMessage(message.content)?.stepLabel }}</div>
            <MarkdownContent class="message__content" mode="markdown"
              :content="parseTaskStructuredMessage(message.content)?.body || ''" />
          </div>
          <div v-else-if="parseTaskStructuredMessage(message.content)?.kind === 'summary'"
            class="message__task-card message__task-card--summary">
            <div class="message__task-card-title">{{ parseTaskStructuredMessage(message.content)?.title }}</div>
            <MarkdownContent class="message__content" mode="markdown"
              :content="parseTaskStructuredMessage(message.content)?.body || ''" />
          </div>
          <div v-else-if="parseTaskStructuredMessage(message.content)?.kind === 'repair'"
            class="message__task-card message__task-card--repair">
            <div class="message__task-card-title">{{ parseTaskStructuredMessage(message.content)?.title }}</div>
            <MarkdownContent class="message__content" mode="markdown"
              :content="parseTaskStructuredMessage(message.content)?.body || ''" />
          </div>
          <div v-else-if="parseTaskStructuredMessage(message.content)?.kind === 'info'"
            class="message__task-card message__task-card--info">
            <div class="message__task-card-title">{{ parseTaskStructuredMessage(message.content)?.title }}</div>
            <MarkdownContent class="message__content" mode="markdown"
              :content="parseTaskStructuredMessage(message.content)?.body || ''" />
          </div>
          <div v-else-if="isTaskPlanMessage(message)" class="message__content">
            <MarkdownContent :content="getTaskPlanIntro(message.content)" />
            <pre v-if="getTaskPlanCode(message.content)" class="message__code"><code>{{ getTaskPlanCode(message.content) }}</code>
  </pre>
          </div>
          <div v-else class="message__content-wrapper">
            <MarkdownContent class="message__content" :mode="message.role === 'assistant' ? 'markdown' : 'auto'"
              :content="message.content" />
            <el-icon v-if="isStreaming(message)" class="message__inline-loading is-loading">
              <Loading />
            </el-icon>
          </div>
        </template>
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

.message--input-form {
  background: rgba(251, 191, 36, 0.08);
  border-color: rgba(251, 191, 36, 0.25);
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
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.message__content-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}

.message__inline-loading {
  font-size: 14px;
  color: #60a5fa;
  animation: spin 1s linear infinite;
}

.message__loading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
}

.message__loading-icon {
  font-size: 18px;
  color: #60a5fa;
  animation: spin 1s linear infinite;
}

.message__loading-text {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.65);
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

.message__task-card {
  display: grid;
  gap: 10px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.message__task-card--input {
  background: rgba(251, 191, 36, 0.08);
  border-color: rgba(251, 191, 36, 0.25);
}

.message__task-card--analyzing {
  background: rgba(30, 64, 175, 0.18);
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

.message__task-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.message__task-card-title {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: rgba(191, 219, 254, 0.88);
  text-transform: uppercase;
}

.message__task-card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.message__task-card-loading {
  font-size: 14px;
  color: #60a5fa;
  animation: spin 1s linear infinite;
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

.message__input-question {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.92);
  line-height: 1.6;
}

.message__input-form-inline {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.message__input-options {
  margin-top: 10px;
}

.message__input-options-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 6px;
}

.message__task-card--answered {
  background: rgba(34, 197, 94, 0.12);
  border-color: rgba(34, 197, 94, 0.3);
}

.message__input-answer {
  margin-top: 10px;
  padding: 10px 14px;
  background: rgba(34, 197, 94, 0.15);
  border-radius: 10px;
  border: 1px solid rgba(34, 197, 94, 0.25);
}

.message__input-answer-label {
  font-size: 12px;
  color: rgba(34, 197, 94, 0.9);
  margin-right: 8px;
}

.message__input-answer-value {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.95);
  font-weight: 500;
}

.message__input-option {
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 8px;
  margin-bottom: 6px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.88);
}

.message__input-form-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message__input-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.message__input-row--options {
  margin-top: 8px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.message__input-field {
  flex: 1;
}

.message__input-options-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.message__input-option-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  cursor: pointer;
  transition: all 0.2s ease;
}

.message__input-option-item:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(96, 165, 250, 0.3);
}

.message__input-option-item.is-selected {
  background: rgba(96, 165, 250, 0.12);
  border-color: rgba(96, 165, 250, 0.5);
}

.message__input-option-radio {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message__input-option-item.is-selected .message__input-option-radio {
  border-color: #60a5fa;
}

.message__input-option-radio-inner {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #60a5fa;
}

.message__input-option-checkbox {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 10px;
}

.message__input-option-item.is-selected .message__input-option-checkbox {
  border-color: #60a5fa;
  background: #60a5fa;
}

.message__input-option-checkbox-inner {
  color: #fff;
  font-weight: bold;
}

.message__input-option-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.88);
}

.message__input-options-readonly {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.message__input-options-readonly-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}

.message__input-option-readonly-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  opacity: 0.7;
}

.message__input-option-readonly-item.is-selected {
  background: rgba(96, 165, 250, 0.12);
  border-color: rgba(96, 165, 250, 0.3);
  opacity: 1;
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
