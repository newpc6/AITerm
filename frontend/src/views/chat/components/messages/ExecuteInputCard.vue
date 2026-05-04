<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  question?: string
  inputType?: 'text' | 'select' | 'multiselect'
  options?: string[]
  placeholder?: string
  loading?: boolean
  answered?: boolean
  answer?: string
}>()

const emit = defineEmits<{
  submit: [value: string]
}>()

const userInputValue = ref('')
const selectedOptions = ref<string[]>([])
const otherInputValue = ref('')
const OTHER_OPTION = '__other__'

watch(
  () => props.question,
  () => {
    userInputValue.value = ''
    selectedOptions.value = []
    otherInputValue.value = ''
  },
  { immediate: true },
)

function handleSubmit() {
  let value = ''
  if (props.inputType === 'multiselect') {
    const actualOptions = selectedOptions.value.filter(opt => opt !== OTHER_OPTION)
    if (selectedOptions.value.includes(OTHER_OPTION) && otherInputValue.value.trim()) {
      actualOptions.push(otherInputValue.value.trim())
    }
    value = actualOptions.join(', ')
  } else if (props.inputType === 'select') {
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

  emit('submit', value)
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
</script>

<template>
  <div class="input-card" :class="{ 'input-card--answered': answered }">
    <div class="input-card__header">
      <div class="input-card__title">{{ answered ? '已输入' : '需要输入' }}</div>
    </div>
    <div v-if="question" class="input-card__question">{{ question }}</div>

    <template v-if="answered">
      <div v-if="options?.length" class="input-card__options-readonly">
        <div class="input-card__options-label">选项：</div>
        <div class="input-card__options-list">
          <div v-for="option in options" :key="option" class="input-card__option-readonly"
            :class="{ 'is-selected': isOptionInAnswer(option, answer || '', inputType) }">
            <span v-if="inputType === 'select'" class="input-card__option-radio">
              <span v-if="isOptionInAnswer(option, answer || '', inputType)" class="input-card__option-radio-inner"></span>
            </span>
            <span v-else class="input-card__option-checkbox">
              <span v-if="isOptionInAnswer(option, answer || '', inputType)" class="input-card__option-checkbox-inner">✓</span>
            </span>
            <span class="input-card__option-text">{{ option }}</span>
          </div>
        </div>
      </div>
      <div class="input-card__answer">
        <span class="input-card__answer-label">您的回答：</span>
        <span class="input-card__answer-value">{{ answer }}</span>
      </div>
    </template>

    <template v-else>
      <div v-if="inputType === 'text'" class="input-card__form">
        <div class="input-card__row">
          <el-input v-model="userInputValue" :placeholder="placeholder || '请输入...'" :disabled="loading"
            class="input-card__field" @keyup.enter="handleSubmit" />
          <el-button type="primary" :loading="loading" :disabled="!userInputValue.trim()" @click="handleSubmit">提交</el-button>
        </div>
      </div>

      <div v-else-if="inputType === 'select'" class="input-card__form">
        <div class="input-card__options-form">
          <div v-for="option in getDisplayOptions(options)" :key="option" class="input-card__option-item"
            :class="{ 'is-selected': userInputValue === option }" @click="handleSelectOption(option)">
            <span class="input-card__option-radio">
              <span v-if="userInputValue === option" class="input-card__option-radio-inner"></span>
            </span>
            <span class="input-card__option-text">{{ option === OTHER_OPTION ? '其他' : option }}</span>
          </div>
        </div>
        <div v-if="isOtherSelected()" class="input-card__row input-card__row--options">
          <el-input v-model="otherInputValue" placeholder="请输入自定义内容" :disabled="loading" class="input-card__field"
            @keyup.enter="handleSubmit" />
          <el-button type="primary" :loading="loading" :disabled="!otherInputValue.trim()" @click="handleSubmit">提交</el-button>
        </div>
        <div v-else class="input-card__row input-card__row--options">
          <el-button type="primary" :loading="loading" :disabled="!userInputValue" @click="handleSubmit">提交</el-button>
        </div>
      </div>

      <div v-else-if="inputType === 'multiselect'" class="input-card__form">
        <div class="input-card__options-form">
          <div v-for="option in getDisplayOptions(options)" :key="option" class="input-card__option-item"
            :class="{ 'is-selected': isOptionSelected(option) }" @click="toggleMultiOption(option)">
            <span class="input-card__option-checkbox">
              <span v-if="isOptionSelected(option)" class="input-card__option-checkbox-inner">✓</span>
            </span>
            <span class="input-card__option-text">{{ option === OTHER_OPTION ? '其他' : option }}</span>
          </div>
        </div>
        <div v-if="isOtherSelectedInMulti()" class="input-card__row input-card__row--options">
          <el-input v-model="otherInputValue" placeholder="请输入自定义内容" :disabled="loading" class="input-card__field"
            @keyup.enter="handleSubmit" />
        </div>
        <div class="input-card__row input-card__row--options">
          <el-button type="primary" :loading="loading"
            :disabled="selectedOptions.length === 0 || (isOtherSelectedInMulti() && !otherInputValue.trim())"
            @click="handleSubmit">提交选择</el-button>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.input-card {
  display: grid;
  gap: 10px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(251, 191, 36, 0.25);
  background: rgba(251, 191, 36, 0.08);
}

.input-card--answered {
  background: var(--color-success-bg);
  border-color: var(--color-success-border);
}

.input-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.input-card__title {
  font-size: var(--font-size-sm);
  font-weight: 700;
  letter-spacing: 0.06em;
  color: rgba(191, 219, 254, 0.88);
  text-transform: uppercase;
}

.input-card__question {
  font-size: 14px;
  color: var(--color-text-secondary);
  line-height: 1.6;
}

.input-card__form {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border-primary);
}

.input-card__row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.input-card__row--options {
  margin-top: 8px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.input-card__field {
  flex: 1;
}

.input-card__options-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-card__option-item {
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

.input-card__option-item:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(96, 165, 250, 0.3);
}

.input-card__option-item.is-selected {
  background: rgba(96, 165, 250, 0.15);
  border-color: rgba(96, 165, 250, 0.4);
}

.input-card__option-radio {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
}

.input-card__option-radio-inner {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #60a5fa;
}

.input-card__option-checkbox {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  color: #60a5fa;
}

.input-card__option-text {
  font-size: 14px;
  color: var(--color-text-primary);
}

.input-card__options-readonly {
  margin-top: 10px;
}

.input-card__options-label {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-bottom: 6px;
}

.input-card__options-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.input-card__option-readonly {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
}

.input-card__option-readonly.is-selected {
  background: rgba(96, 165, 250, 0.15);
}

.input-card__answer {
  margin-top: 10px;
  padding: 10px 14px;
  background: rgba(34, 197, 94, 0.15);
  border-radius: var(--border-radius-md);
  border: 1px solid rgba(34, 197, 94, 0.25);
}

.input-card__answer-label {
  font-size: var(--font-size-sm);
  color: rgba(34, 197, 94, 0.9);
  margin-right: var(--spacing-sm);
}

.input-card__answer-value {
  font-size: var(--font-size-md);
  color: var(--color-text-primary);
  font-weight: 500;
}
</style>
