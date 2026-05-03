<script setup lang="ts">
import { ref, watch } from 'vue'
import { VideoPlay } from '@element-plus/icons-vue'
import type { ToolCreate } from '@/types/tool'
import { executeTool } from '@/api/aiterm'
import CodeEditor from '@/components/CodeEditor.vue'

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

watch(() => props.form, (newForm) => {
  localForm.value = { ...newForm }
}, { deep: true })

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
      testResult.value = JSON.stringify(result, null, 2)
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
          <CodeEditor v-model="testArguments" />
        </div>
        <div class="test-output">
          <label>结果</label>
          <pre class="result-display">{{ testResult || '执行结果将显示在这里' }}</pre>
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
}

.code-editor-container {
  width: 100%;
  height: 250px;
}

.test-section {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--color-border-primary);
}

.test-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.test-header h3 {
  margin: 0;
  font-size: 16px;
}

.test-content {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.test-input,
.test-output {
  display: flex;
  flex-direction: column;
}

.test-input {
  height: 250px;
}

.test-input label,
.test-output label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 8px;
  color: var(--color-text-secondary);
}

.result-display {
  flex: 1;
  padding: 12px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 14px;
  line-height: 1.5;
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid var(--color-border-primary);
  border-radius: 8px;
  color: var(--color-text-primary);
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  overflow: auto;
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
</style>
