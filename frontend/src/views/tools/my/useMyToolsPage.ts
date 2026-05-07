import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getMyTools, toggleMyTool, getTemplates, importTemplates, createMyTool, updateMyTool, deleteMyTool } from '@/api/aiterm'
import type { UserTool, ToolCreate, ToolUpdate, Tool } from '@/types/tool'

export function useMyToolsPage() {
  const loading = ref(false)
  const tools = ref<UserTool[]>([])
  const filterEnabled = ref<string>('all')

  const createDialogVisible = ref(false)
  const createTitle = ref('新建工具')
  const editingId = ref<string | null>(null)
  const saving = ref(false)
  const form = ref<ToolCreate>({
    name: '', display_name: '', description: '',
    code: 'def execute(arguments):\n    """\n    arguments: dict\n    """\n    return {"result": "success"}',
    enabled: true, sandbox_only: false,
  })

  const templateDialogVisible = ref(false)
  const templates = ref<Tool[]>([])
  const templateLoading = ref(false)
  const selectedTemplates = ref<string[]>([])

  async function loadTools() {
    loading.value = true
    try { tools.value = await getMyTools() } catch { ElMessage.error('加载失败') }
    finally { loading.value = false }
  }

  const filteredTools = ref<UserTool[]>([])

  function applyFilter() {
    if (filterEnabled.value === 'enabled') {
      filteredTools.value = tools.value.filter(t => t.enabled)
    } else if (filterEnabled.value === 'disabled') {
      filteredTools.value = tools.value.filter(t => !t.enabled)
    } else {
      filteredTools.value = tools.value
    }
  }

  async function handleToggle(tool: UserTool) {
    try {
      await toggleMyTool(tool.tool_id)
      await loadTools()
      applyFilter()
      ElMessage.success(tool.enabled ? '已禁用' : '已启用')
    } catch { ElMessage.error('操作失败') }
  }

  function openCreateDialog() {
    editingId.value = null
    createTitle.value = '新建工具'
    form.value = {
      name: '', display_name: '', description: '',
      code: 'def execute(arguments):\n    """\n    arguments: dict\n    """\n    return {"result": "success"}',
      enabled: true, sandbox_only: false,
    }
    createDialogVisible.value = true
  }

  function openEditDialog(tool: UserTool) {
    editingId.value = tool.tool_id
    createTitle.value = '编辑工具'
    form.value = {
      name: tool.tool_name || '', display_name: tool.tool_display_name || '',
      description: tool.tool_description || '', code: '',
      enabled: tool.enabled, sandbox_only: false,
    }
    createDialogVisible.value = true
  }

  async function handleSave() {
    if (!form.value.name.trim()) return
    saving.value = true
    try {
      if (editingId.value) {
        const update: ToolUpdate = {
          name: form.value.name, display_name: form.value.display_name || undefined,
          description: form.value.description || undefined, code: form.value.code,
          enabled: form.value.enabled, sandbox_only: form.value.sandbox_only,
        }
        await updateMyTool(editingId.value, update)
        ElMessage.success('更新成功')
      } else {
        await createMyTool(form.value)
        ElMessage.success('创建成功')
      }
      createDialogVisible.value = false
      await loadTools()
      applyFilter()
    } catch { ElMessage.error('保存失败') }
    finally { saving.value = false }
  }

  async function handleDelete(tool: UserTool) {
    try {
      await ElMessageBox.confirm(`确定删除 "${tool.tool_name}" 吗？`, '删除确认', { type: 'warning' })
      await deleteMyTool(tool.tool_id)
      ElMessage.success('已删除')
      await loadTools()
      applyFilter()
    } catch { /* cancelled */ }
  }

  async function openTemplateDialog() {
    templateLoading.value = true
    templateDialogVisible.value = true
    selectedTemplates.value = []
    try { templates.value = await getTemplates() } catch { ElMessage.error('加载模板失败') }
    finally { templateLoading.value = false }
  }

  async function handleImportTemplates() {
    if (selectedTemplates.value.length === 0) { ElMessage.warning('请选择模板'); return }
    try {
      await importTemplates(selectedTemplates.value)
      ElMessage.success(`成功导入 ${selectedTemplates.value.length} 个工具`)
      templateDialogVisible.value = false
      await loadTools()
      applyFilter()
    } catch { ElMessage.error('导入失败') }
  }

  onMounted(async () => {
    await loadTools()
    applyFilter()
  })

  return {
    loading, tools, filteredTools, filterEnabled, applyFilter,
    handleToggle, openCreateDialog, openEditDialog, handleSave, handleDelete,
    createDialogVisible, createTitle, editingId, saving, form,
    templateDialogVisible, templates, templateLoading, selectedTemplates,
    openTemplateDialog, handleImportTemplates,
  }
}
