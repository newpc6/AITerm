<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { Tool, ToolCreate, ToolUpdate } from '@/types/tool'
import { getTools, createTool, updateTool, deleteTool } from '@/api/aiterm'
import ToolForm from './components/ToolForm.vue'
import ToolTable from './components/ToolTable.vue'

const tools = ref<Tool[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新建工具')
const currentToolId = ref<string | null>(null)
const successMessage = ref('')
const errorMessage = ref('')

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
  enabled: true,
  sandbox_only: false
})

const isEdit = computed(() => !!currentToolId.value)
const toolCount = computed(() => tools.value.length)

async function loadTools() {
  loading.value = true
  errorMessage.value = ''
  try {
    tools.value = await getTools()
  } catch {
    errorMessage.value = '加载工具列表失败'
  } finally {
    loading.value = false
  }
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
          <el-button type="primary" @click="openCreateDialog">新建工具</el-button>
        </div>
      </div>
      <ToolTable
        :tools="tools"
        :loading="loading"
        @edit="openEditDialog"
        @delete="handleDelete"
        @toggle-enabled="handleToggleEnabled"
      />
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="60%" top="5vh" :close-on-click-modal="false" destroy-on-close>
      <ToolForm
        :form="form"
        :is-edit="isEdit"
        :tool-id="currentToolId"
        @submit="handleSubmit"
        @cancel="dialogVisible = false"
      />
    </el-dialog>
  </section>
</template>

<style scoped>
@use '@/styles/global.scss';
</style>
