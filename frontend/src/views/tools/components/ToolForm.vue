<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { VideoPlay, Plus, Delete } from '@element-plus/icons-vue'
import type { ToolCreate, ToolParameter, ToolParameters } from '@/types/tool'
import { executeTool } from '@/api/aiterm'
import CodeEditor from '@/components/CodeEditor.vue'
import MarkdownContent from '@/components/MarkdownContent.vue'

const props = defineProps<{
  form: ToolCreate
  isEdit: boolean
  toolId: string | null
}>()

const emit = defineEmits<{
  submit: [payload: ToolCreate]
  cancel: []
}>()

const localForm = ref<ToolCreate>({ ...props.form })
const saving = ref(false)
const testArguments = ref('{\n  \n}')
const testResult = ref('')
const testLoading = ref(false)

const paramTypes = ['string', 'number', 'integer', 'boolean', 'array', 'object']

interface ParamItem {
  name: string
  type: string
  description: string
  required: boolean
  default?: string
  enum?: string
}

const paramItems = ref<ParamItem[]>([])

watch(() => props.form, (newForm) => {
  localForm.value = { ...newForm }
  loadParametersFromForm()
}, { deep: true, immediate: true })

function loadParametersFromForm() {
  paramItems.value = []
  if (localForm.value.parameters?.properties) {
    const required = localForm.value.parameters.required || []
    for (const [name, param] of Object.entries(localForm.value.parameters.properties)) {
      paramItems.value.push({
        name,
        type: param.type || 'string',
        description: param.description || '',
        required: required.includes(name),
        default: param.default != null ? String(param.default) : '',
        enum: param.enum?.join(', ') || ''
      })
    }
  }
  generateTestArguments()
}

function generateTestArguments() {
  if (paramItems.value.length === 0) {
    testArguments.value = '{\n  \n}'
    return
  }

  const args: Record<string, unknown> = {}
  for (const param of paramItems.value) {
    if (!param.name.trim()) continue

    if (param.default.trim()) {
      if (param.type === 'number' || param.type === 'integer') {
        args[param.name] = Number(param.default)
      } else if (param.type === 'boolean') {
        args[param.name] = param.default.toLowerCase() === 'true'
      } else {
        args[param.name] = param.default
      }
    } else {
      switch (param.type) {
        case 'number':
        case 'integer':
          args[param.name] = 0
          break
        case 'boolean':
          args[param.name] = false
          break
        case 'array':
          args[param.name] = []
          break
        case 'object':
          args[param.name] = {}
          break
        default:
          args[param.name] = ''
      }
    }
  }

  testArguments.value = JSON.stringify(args, null, 2)
}

function addParameter() {
  paramItems.value.push({
    name: '',
    type: 'string',
    description: '',
    required: true,
    default: '',
    enum: ''
  })
}

function removeParameter(index: number) {
  paramItems.value.splice(index, 1)
  generateTestArguments()
}

watch(paramItems, () => {
  generateTestArguments()
}, { deep: true })

function buildParameters(): ToolParameters | undefined {
  if (paramItems.value.length === 0) {
    return undefined
  }

  const properties: Record<string, ToolParameter> = {}
  const required: string[] = []

  for (const item of paramItems.value) {
    if (!item.name.trim()) continue

    const param: ToolParameter = {
      type: item.type,
      description: item.description
    }

    if (item.default.trim()) {
      if (item.type === 'number' || item.type === 'integer') {
        param.default = Number(item.default)
      } else if (item.type === 'boolean') {
        param.default = item.default.toLowerCase() === 'true'
      } else {
        param.default = item.default
      }
    }

    if (item.enum.trim()) {
      param.enum = item.enum.split(',').map(e => e.trim()).filter(e => e)
    }

    properties[item.name] = param
    if (item.required) {
      required.push(item.name)
    }
  }

  return {
    type: 'object',
    properties,
    required
  }
}

const paramCount = computed(() => paramItems.value.filter(p => p.name.trim()).length)

async function handleTest() {
  testLoading.value = true
  testResult.value = ''
  try {
    let args = {}
    if (testArguments.value.trim()) {
      args = JSON.parse(testArguments.value)
    }

    if (props.toolId) {
      const result = await executeTool(props.toolId, args)
      const jsonStr = JSON.stringify(result, null, 2)
      testResult.value = `\`\`\`json\n${jsonStr}\n\`\`\``
    } else {
      testResult.value = '请先保存工具后再测试'
    }
  } catch (e: unknown) {
    const message = (e as Error).message || '测试失败'
    testResult.value = `错误: ${message}`
  } finally {
    testLoading.value = false
  }
}

async function handleSubmit() {
  if (!localForm.value.name.trim()) {
    return
  }
  localForm.value.parameters = buildParameters()
  saving.value = true
  try {
    emit('submit', localForm.value)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="tool-form">
    <el-form :model="localForm" label-width="100px">
      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="工具名称" required>
            <el-input v-model="localForm.name" placeholder="如: query_database" :disabled="isEdit" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="显示名称">
            <el-input v-model="localForm.display_name" placeholder="如: 查询数据库" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="描述">
        <el-input v-model="localForm.description" type="textarea" :rows="2" placeholder="描述这个工具的功能，供大模型理解何时调用" />
      </el-form-item>
      <el-form-item label="状态">
        <el-switch v-model="localForm.enabled" active-text="启用" inactive-text="禁用" />
      </el-form-item>
      <el-form-item label="沙盒限制">
        <el-switch v-model="localForm.sandbox_only" active-text="是" inactive-text="否" />
        <div class="form-tip">启用后，工具只能在沙盒路径内执行文件操作</div>
      </el-form-item>
      <el-form-item label="参数定义">
        <div class="params-editor">
          <div class="params-header">
            <span class="params-count">共 {{ paramCount }} 个参数</span>
            <el-button type="primary" size="small" :icon="Plus" @click="addParameter">添加参数</el-button>
          </div>
          <div v-if="paramItems.length > 0" class="params-list">
            <div v-for="(param, index) in paramItems" :key="index" class="param-item">
              <div class="param-row">
                <div class="param-field">
                  <span class="param-label">参数名</span>
                  <el-input v-model="param.name" placeholder="如: file_path" class="param-name" />
                </div>
                <div class="param-field">
                  <span class="param-label">类型</span>
                  <el-select v-model="param.type" class="param-type">
                    <el-option v-for="t in paramTypes" :key="t" :label="t" :value="t" />
                  </el-select>
                </div>
                <div class="param-field param-field-checkbox">
                  <el-checkbox v-model="param.required" label="必填" />
                </div>
                <el-button type="danger" :icon="Delete" circle size="small" @click="removeParameter(index)" />
              </div>
              <div class="param-row">
                <div class="param-field param-field-full">
                  <span class="param-label">描述</span>
                  <el-input v-model="param.description" placeholder="参数描述，供大模型理解参数用途" class="param-desc" />
                </div>
              </div>
              <div class="param-row param-extras">
                <div class="param-field">
                  <span class="param-label">默认值</span>
                  <el-input v-model="param.default" placeholder="可选" class="param-default" />
                </div>
                <div class="param-field">
                  <span class="param-label">枚举值</span>
                  <el-input v-model="param.enum" placeholder="逗号分隔，可选" class="param-enum" />
                </div>
              </div>
            </div>
          </div>
          <div v-else class="params-empty">
            <span>暂无参数，点击"添加参数"定义工具需要的参数</span>
          </div>
        </div>
      </el-form-item>
      <el-form-item label="代码">
        <div class="code-editor-container">
          <CodeEditor v-model="localForm.code" />
        </div>
      </el-form-item>
    </el-form>

    <div class="test-section">
      <div class="test-header">
        <h3>测试工具</h3>
        <el-button type="primary" :icon="VideoPlay" :loading="testLoading" @click="handleTest">
          执行测试
        </el-button>
      </div>
      <div class="test-content">
        <div class="test-input">
          <label>参数 (JSON)</label>
          <CodeEditor v-model="testArguments" language="json" />
        </div>
        <div class="test-output">
          <label>结果</label>
          <div class="result-display">
            <MarkdownContent v-if="testResult" :content="testResult" mode="auto" />
            <span v-else class="result-placeholder">执行结果将显示在这里</span>
          </div>
        </div>
      </div>
    </div>

    <div class="form-actions">
      <el-button @click="emit('cancel')">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSubmit">保存</el-button>
    </div>
  </div>
</template>

<style scoped>
.tool-form {
  max-height: 70vh;
  overflow-y: auto;
  overflow-x: hidden;
}

.tool-form :deep(.el-form-item__content) {
  max-width: 100%;
}

.code-editor-container {
  width: 100%;
  height: 280px;
}

.test-section {
  margin-top: 20px;
  padding: 12px;
  margin-left: 100px;
  border-top: 1px solid var(--color-border-primary);
  background: var(--color-bg-secondary);
  border-radius: 8px;
  width: calc(100% - 100px);
  box-sizing: border-box;
  overflow: hidden;
}

.test-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.test-header h3 {
  margin: 0;
  font-size: 14px;
  color: var(--color-text-secondary);
}

.test-content {
  display: flex;
  gap: 10px;
  width: 100%;
}

.test-input,
.test-output {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  max-width: calc(50% - 5px);
}

.test-input {
  min-height: 180px;
}

.test-output {
  min-height: 180px;
}

.test-input label,
.test-output label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 6px;
  color: var(--color-text-secondary);
}

.test-input :deep(.code-editor-wrapper) {
  flex: 1;
  min-height: 150px;
}

.result-display {
  flex: 1;
  padding: 10px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  line-height: 1.4;
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid var(--color-border-primary);
  border-radius: 6px;
  color: var(--color-text-primary);
  overflow: auto;
  min-height: 120px;
}

.result-placeholder {
  color: var(--color-text-secondary);
  font-style: italic;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--color-border-primary);
}

.form-tip {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}

.params-editor {
  width: 100%;
  min-width: 0;
}

.params-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.params-count {
  font-size: 14px;
  color: var(--color-text-secondary);
}

.params-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.param-item {
  flex: 1 1 calc(50% - 6px);
  min-width: 280px;
  max-width: calc(25% - 9px);
  padding: 12px;
  background: var(--color-bg-secondary);
  border-radius: 8px;
  border: 1px solid var(--color-border);
}

.param-row {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.param-row:last-child {
  margin-bottom: 0;
}

.param-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1 1 calc(25% - 12px);
  min-width: 120px;
}

.param-field-full {
  flex: 1 1 100%;
  min-width: 200px;
}

.param-field-checkbox {
  flex: 0 0 auto;
  min-width: 60px;
  padding-top: 22px;
}

.param-label {
  font-size: 12px;
  color: var(--color-text-secondary);
  font-weight: 500;
}

.param-name {
  width: 100%;
}

.param-type {
  width: 100%;
}

.param-desc {
  width: 100%;
}

.param-extras {
  margin-top: 8px;
}

.param-default {
  width: 100%;
}

.param-enum {
  width: 100%;
}

.params-empty {
  padding: 24px;
  text-align: center;
  color: var(--color-text-secondary);
  background: var(--color-bg-secondary);
  border-radius: 8px;
  border: 1px dashed var(--color-border);
}
</style>
