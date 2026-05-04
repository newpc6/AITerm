<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { SuccessFilled, CircleCloseFilled } from '@element-plus/icons-vue'
import type { Tool, ToolCreate, ToolUpdate, BuiltinTool, ToolsImportResponse } from '@/types/tool'
import { getTools, createTool, updateTool, deleteTool, exportTools, importTools, getBuiltinTools, importBuiltinTools } from '@/api/aiterm'
import ToolForm from './components/ToolForm.vue'
import ToolTable from './components/ToolTable.vue'
import Pagination from '@/components/Pagination.vue'

const allTools = ref<Tool[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新建工具')
const currentToolId = ref<string | null>(null)
const successMessage = ref('')
const errorMessage = ref('')

const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const selectedTools = ref<Tool[]>([])

const importDialogVisible = ref(false)
const importJsonContent = ref('')
const importOverwrite = ref(false)
const importLoading = ref(false)
const importFile = ref<File | null>(null)
const importResults = ref<ToolsImportResponse | null>(null)

const builtinDialogVisible = ref(false)
const builtinTools = ref<BuiltinTool[]>([])
const builtinLoading = ref(false)
const selectedBuiltinTools = ref<string[]>([])
const builtinOverwrite = ref(false)

const form = ref<ToolCreate>({
  name: '',
  display_name: '',
  description: '',
  code: `def execute(arguments):
    """
    arguments: dict - 工具参数
    返回: 工具执行结果
    """
    # 在这里编写你的工具逻辑
    return {"result": "success"}
`,
  parameters: undefined,
  config_schema: undefined,
  enabled: true,
  sandbox_only: false
})

const isEdit = computed(() => !!currentToolId.value)
const toolCount = computed(() => total.value)
const tools = computed(() => {
  const start = (page.value - 1) * pageSize.value
  const end = start + pageSize.value
  return allTools.value.slice(start, end)
})

async function loadTools() {
  loading.value = true
  errorMessage.value = ''
  try {
    allTools.value = await getTools()
    total.value = allTools.value.length
  } catch {
    errorMessage.value = '加载工具列表失败'
  } finally {
    loading.value = false
  }
}

function handlePageChange(newPage: number) {
  page.value = newPage
}

function handlePageSizeChange(newSize: number) {
  pageSize.value = newSize
  page.value = 1
}

function openCreateDialog() {
  currentToolId.value = null
  dialogTitle.value = '新建工具'
  form.value = {
    name: '',
    display_name: '',
    description: '',
    code: `def execute(arguments):
    """
    arguments: dict - 工具参数
    返回: 工具执行结果
    """
    # 在这里编写你的工具逻辑
    return {"result": "success"}
`,
    parameters: undefined,
    config_schema: undefined,
    enabled: true,
    sandbox_only: false
  }
  successMessage.value = ''
  errorMessage.value = ''
  dialogVisible.value = true
}

function openEditDialog(tool: Tool) {
  currentToolId.value = tool.id
  dialogTitle.value = '编辑工具'
  form.value = {
    name: tool.name,
    display_name: tool.display_name || '',
    description: tool.description || '',
    code: tool.code,
    parameters: tool.parameters,
    config_schema: tool.config_schema,
    enabled: tool.enabled,
    sandbox_only: tool.sandbox_only
  }
  successMessage.value = ''
  errorMessage.value = ''
  dialogVisible.value = true
}

async function handleSubmit(payload: ToolCreate) {
  try {
    if (isEdit.value && currentToolId.value) {
      const updatePayload: ToolUpdate = {
        name: payload.name,
        display_name: payload.display_name || undefined,
        description: payload.description || undefined,
        code: payload.code,
        parameters: payload.parameters,
        config_schema: payload.config_schema,
        enabled: payload.enabled,
        sandbox_only: payload.sandbox_only
      }
      await updateTool(currentToolId.value, updatePayload)
      successMessage.value = '更新成功'
    } else {
      await createTool(payload)
      successMessage.value = '创建成功'
    }
    dialogVisible.value = false
    await loadTools()
  } catch (e: unknown) {
    const message = (e as { response?: { data?: { message?: string } } })?.response?.data?.message || '操作失败'
    errorMessage.value = message
  }
}

async function handleDelete(tool: Tool) {
  try {
    await ElMessageBox.confirm(`确定要删除工具 "${tool.display_name || tool.name}" 吗？`, '删除确认', {
      type: 'warning'
    })
    await deleteTool(tool.id)
    successMessage.value = '删除成功'
    await loadTools()
  } catch {
    // cancelled
  }
}

async function handleToggleEnabled(tool: Tool) {
  try {
    await updateTool(tool.id, { enabled: !tool.enabled })
    successMessage.value = tool.enabled ? '已禁用' : '已启用'
    await loadTools()
  } catch {
    errorMessage.value = '操作失败'
  }
}

function handleExportSingle(tool: Tool) {
  const exportData = [{
    name: tool.name,
    display_name: tool.display_name,
    description: tool.description,
    code: tool.code,
    parameters: tool.parameters,
    config_schema: tool.config_schema,
    enabled: tool.enabled,
    sandbox_only: tool.sandbox_only
  }]
  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `tool_${tool.name}.json`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('导出成功')
}

async function handleExportSelected() {
  if (selectedTools.value.length === 0) {
    ElMessage.warning('请先选择要导出的工具')
    return
  }
  const exportData = selectedTools.value.map(tool => ({
    name: tool.name,
    display_name: tool.display_name,
    description: tool.description,
    code: tool.code,
    parameters: tool.parameters,
    config_schema: tool.config_schema,
    enabled: tool.enabled,
    sandbox_only: tool.sandbox_only
  }))
  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'tools_export.json'
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success(`成功导出 ${selectedTools.value.length} 个工具`)
}

async function handleExportAll() {
  try {
    const data = await exportTools()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'tools_export.json'
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch {
    ElMessage.error('导出失败')
  }
}

function openImportDialog() {
  importJsonContent.value = ''
  importOverwrite.value = false
  importFile.value = null
  importResults.value = null
  importDialogVisible.value = true
}

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  if (target.files && target.files[0]) {
    importFile.value = target.files[0]
  }
}

async function handleImport() {
  if (!importJsonContent.value && !importFile.value) {
    ElMessage.warning('请输入JSON内容或选择文件')
    return
  }

  importLoading.value = true
  try {
    const result = await importTools({
      file: importFile.value || undefined,
      json_content: importFile.value ? undefined : importJsonContent.value,
      overwrite: importOverwrite.value
    })
    importResults.value = result
    if (result.imported > 0) {
      await loadTools()
    }
    ElMessage.success(`导入完成: 成功 ${result.imported}, 跳过 ${result.skipped}, 失败 ${result.failed}`)
  } catch (e: unknown) {
    const message = (e as { response?: { data?: { message?: string } } })?.response?.data?.message || '导入失败'
    ElMessage.error(message)
  } finally {
    importLoading.value = false
  }
}

async function openBuiltinDialog() {
  builtinLoading.value = true
  builtinDialogVisible.value = true
  selectedBuiltinTools.value = []
  builtinOverwrite.value = false
  try {
    builtinTools.value = await getBuiltinTools()
  } catch {
    ElMessage.error('加载内置工具失败')
  } finally {
    builtinLoading.value = false
  }
}

async function handleImportBuiltin() {
  if (selectedBuiltinTools.value.length === 0) {
    ElMessage.warning('请选择要导入的工具')
    return
  }

  builtinLoading.value = true
  try {
    const result = await importBuiltinTools(selectedBuiltinTools.value, builtinOverwrite.value)
    if (result.imported > 0) {
      await loadTools()
    }
    ElMessage.success(`导入完成: 成功 ${result.imported}, 跳过 ${result.skipped}, 失败 ${result.failed}`)
    builtinDialogVisible.value = false
  } catch (e: unknown) {
    const message = (e as { response?: { data?: { message?: string } } })?.response?.data?.message || '导入失败'
    ElMessage.error(message)
  } finally {
    builtinLoading.value = false
  }
}

onMounted(() => {
  loadTools()
})
</script>

<template>
  <section class="page">
    <div class="hero">
      <p class="label">工具</p>
      <h1>工具管理</h1>
      <p>管理自定义工具，支持大模型调用工具获取信息或执行操作。</p>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="warning" show-icon :closable="false" />
    <el-alert v-if="successMessage" :title="successMessage" type="success" show-icon :closable="false" />

    <div class="card">
      <div class="page-header">
        <div>
          <p class="label">工具列表</p>
          <div class="value">{{ toolCount }} 个工具</div>
        </div>
        <div class="page-header__actions">
          <el-button :loading="loading" @click="loadTools">刷新</el-button>
          <el-button @click="openBuiltinDialog">导入内置工具</el-button>
          <el-button @click="openImportDialog">导入</el-button>
          <el-button @click="handleExportSelected" :disabled="selectedTools.length === 0">
            导出选中 ({{ selectedTools.length }})
          </el-button>
          <el-button @click="handleExportAll">导出全部</el-button>
          <el-button type="primary" @click="openCreateDialog">新建工具</el-button>
        </div>
      </div>
      <ToolTable :tools="tools" :loading="loading" @edit="openEditDialog" @delete="handleDelete"
        @toggle-enabled="handleToggleEnabled" @export="handleExportSingle" @selection-change="selectedTools = $event" />
      <Pagination :page="page" :page-size="pageSize" :total="total" @update:page="handlePageChange"
        @update:page-size="handlePageSizeChange" />
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="60%" top="5vh" :close-on-click-modal="false"
      destroy-on-close>
      <ToolForm :form="form" :is-edit="isEdit" :tool-id="currentToolId" @submit="handleSubmit"
        @cancel="dialogVisible = false" />
    </el-dialog>

    <el-dialog v-model="importDialogVisible" title="导入工具" width="600px" :close-on-click-modal="false">
      <el-form label-position="top">
        <el-form-item label="选择文件">
          <input type="file" accept=".json" @change="handleFileChange" class="file-input" />
        </el-form-item>
        <div class="divider">或</div>
        <el-form-item label="JSON内容">
          <el-input v-model="importJsonContent" type="textarea" :rows="10" placeholder="粘贴工具JSON内容（支持单个对象或数组）..."
            :disabled="!!importFile" />
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="importOverwrite">覆盖已存在的工具</el-checkbox>
        </el-form-item>
      </el-form>
      <div v-if="importResults" class="import-results">
        <el-alert type="info" :closable="false">
          <template #title>
            导入结果: 成功 {{ importResults.imported }}, 跳过 {{ importResults.skipped }}, 失败 {{ importResults.failed }}
          </template>
        </el-alert>
        <div v-if="importResults.results.length > 0" class="result-list">
          <div v-for="(item, index) in importResults.results" :key="index" class="result-item">
            <el-icon v-if="item.success" color="green">
              <SuccessFilled />
            </el-icon>
            <el-icon v-else color="red">
              <CircleCloseFilled />
            </el-icon>
            <span>{{ item.name }}</span>
            <span v-if="item.action" class="action">({{ item.action }})</span>
            <span v-if="item.error" class="error">- {{ item.error }}</span>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="importLoading" @click="handleImport">导入</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="builtinDialogVisible" title="导入内置工具" width="800px" :close-on-click-modal="false">
      <div v-loading="builtinLoading">
        <div class="builtin-hint">
          内置工具是系统预置的工具JSON文件，存放在 <code>backend/tools/</code> 目录下。选择需要的工具导入到数据库中即可使用。
        </div>
        <div class="builtin-header">
          <span class="builtin-count">共 {{ builtinTools.length }} 个内置工具</span>
          <div class="builtin-select-actions">
            <el-button size="small" @click="selectedBuiltinTools = builtinTools.map(t => t.filename)">全选</el-button>
            <el-button size="small" @click="selectedBuiltinTools = []">全不选</el-button>
          </div>
        </div>
        <el-checkbox-group v-model="selectedBuiltinTools" class="builtin-tools-list">
          <div v-for="(tool, index) in builtinTools" :key="tool.filename" class="builtin-tool-item">
            <span class="builtin-tool-index">{{ index + 1 }}</span>
            <el-checkbox :value="tool.filename">
              <div class="builtin-tool-info">
                <div class="builtin-tool-name">{{ tool.display_name || tool.name }}</div>
                <div class="builtin-tool-desc">{{ tool.description }}</div>
              </div>
            </el-checkbox>
          </div>
        </el-checkbox-group>
        <div class="builtin-actions">
          <el-checkbox v-model="builtinOverwrite">覆盖已存在的工具</el-checkbox>
        </div>
      </div>
      <template #footer>
        <el-button @click="builtinDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="builtinLoading" :disabled="selectedBuiltinTools.length === 0"
          @click="handleImportBuiltin">
          导入 ({{ selectedBuiltinTools.length }})
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
@use '@/styles/global.scss';

.file-input {
  width: 100%;
  padding: 8px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-bg);
  color: var(--color-text);
}

.divider {
  text-align: center;
  color: var(--color-text-secondary);
  margin: 16px 0;
}

.import-results {
  margin-top: 16px;
}

.result-list {
  margin-top: 12px;
  max-height: 200px;
  overflow-y: auto;
}

.result-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 13px;
}

.result-item .action {
  color: var(--color-text-secondary);
}

.result-item .error {
  color: var(--color-danger);
}

.builtin-hint {
  margin-bottom: 16px;
  padding: 12px;
  background: var(--color-bg-secondary);
  border-radius: 8px;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.builtin-hint code {
  background: var(--color-bg);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', monospace;
}

.builtin-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: var(--color-bg-secondary);
  border-radius: 8px;
}

.builtin-count {
  font-size: 14px;
  color: var(--color-text-secondary);
}

.builtin-select-actions {
  display: flex;
  gap: 8px;
}

.builtin-tools-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 400px;
  overflow-y: auto;
}

.builtin-tool-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  transition: all 0.2s;
}

.builtin-tool-item:hover {
  border-color: var(--color-primary);
}

.builtin-tool-index {
  min-width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-secondary);
  border-radius: 4px;
  font-size: 12px;
  color: var(--color-text-secondary);
  font-weight: 500;
}

.builtin-tool-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.builtin-tool-name {
  font-weight: 500;
}

.builtin-tool-desc {
  font-size: 12px;
  color: var(--color-text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.builtin-actions {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border);
}
</style>
