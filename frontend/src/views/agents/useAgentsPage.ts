import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getAgents, createAgent, updateAgent, deleteAgent, cloneAgent, setDefaultAgent, getModels, getCurrentUser } from '@/api/aiterm'
import { http } from '@/api/http'
import type { AgentItem, AgentPayload, ModelConfigItem } from '@/types/api'

interface SkillItem {
  id: string
  name: string
  display_name: string
}

export function useAgentsPage() {
  const loading = ref(false)
  const agents = ref<AgentItem[]>([])
  const models = ref<ModelConfigItem[]>([])
  const skills = ref<SkillItem[]>([])
  const currentUserId = ref('')
  const isAdmin = ref(false)
  const filterScope = ref<string>('my')

  const dialogVisible = ref(false)
  const viewDialogVisible = ref(false)
  const viewAgent = ref<AgentItem | null>(null)
  const dialogTitle = ref('新建智能体')
  const editingId = ref<string | null>(null)
  const saving = ref(false)
  const form = ref<AgentPayload>({
    name: '',
    description: '',
    icon: 'robot',
    model_id: '',
    skill_ids: [],
    system_prompt: '',
    temperature: 0.7,
    max_iterations: 10,
    is_public: false,
    is_template: false,
    scope: 'private',
  })

  const filteredAgents = ref<AgentItem[]>([])

  async function load() {
    loading.value = true
    try {
      agents.value = await getAgents()
      try { models.value = ((await getModels()) as { items: ModelConfigItem[] }).items || [] } catch { models.value = [] }
      try {
        const { data } = await http.get('/api/v1/skills/installed/list')
        skills.value = (data as any).data || []
      } catch { skills.value = [] }
      try { const u = await getCurrentUser(); currentUserId.value = u.id; isAdmin.value = u.role === 'admin' } catch { currentUserId.value = '' }
    } catch { ElMessage.error('加载失败') }
    finally { loading.value = false; applyFilter() }
  }

  function applyFilter() {
    if (filterScope.value === 'my') {
      filteredAgents.value = agents.value.filter((a) => a.scope === 'private' || a.installed)
    } else if (filterScope.value === 'template') {
      filteredAgents.value = agents.value.filter((a) => a.is_template && a.status === 'approved')
    } else if (filterScope.value === 'pending') {
      filteredAgents.value = agents.value.filter((a) => a.status === 'pending')
    } else {
      filteredAgents.value = agents.value
    }
  }

  function openCreate() {
    editingId.value = null; dialogTitle.value = '新建智能体'
    form.value = {
      name: '', description: '', icon: 'robot', model_id: models.value[0]?.id || '',
      skill_ids: [], system_prompt: '', temperature: 0.7, max_iterations: 10,
      is_public: false, is_template: false, scope: 'private',
    }
    dialogVisible.value = true
  }

  function openEdit(agent: AgentItem) {
    editingId.value = agent.id; dialogTitle.value = '编辑智能体'
    form.value = {
      name: agent.name, description: agent.description, icon: agent.icon,
      model_id: agent.model_id || '', skill_ids: agent.skill_ids || [],
      system_prompt: agent.system_prompt, temperature: agent.temperature,
      max_iterations: agent.max_iterations,
      is_public: agent.is_public, is_template: agent.is_template, scope: agent.scope,
    }
    dialogVisible.value = true
  }

  function openView(agent: AgentItem) {
    viewAgent.value = agent
    viewDialogVisible.value = true
  }

  async function handleSave() {
    if (!form.value.name.trim()) return
    saving.value = true
    try {
      if (editingId.value) {
        await updateAgent(editingId.value, form.value)
        ElMessage.success('更新成功')
      } else {
        await createAgent(form.value)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false; await load()
    } catch { ElMessage.error('保存失败') }
    finally { saving.value = false }
  }

  async function handleDelete(id: string) {
    try {
      await ElMessageBox.confirm('确定删除该智能体吗？', '删除确认', { type: 'warning' })
      await deleteAgent(id)
      ElMessage.success('已删除'); await load()
    } catch { /* cancelled */ }
  }

  async function handleClone(id: string) {
    try { await cloneAgent(id); ElMessage.success('已克隆'); await load() } catch { ElMessage.error('克隆失败') }
  }

  async function handleSetDefault(id: string) {
    try { await setDefaultAgent(id); ElMessage.success('已设为默认'); await load() } catch { ElMessage.error('设置失败') }
  }

  async function handleSubmit(id: string) {
    try { await http.post(`/api/v1/agents/${id}/submit`); ElMessage.success('已提交审核'); await load() } catch { ElMessage.error('提交失败') }
  }

  async function handleWithdraw(id: string) {
    try { await http.post(`/api/v1/agents/${id}/withdraw`); ElMessage.success('已撤回'); await load() } catch { ElMessage.error('撤回失败') }
  }

  async function handleReview(id: string, approved: boolean) {
    try { await http.post(`/api/v1/agents/${id}/review`, { approved, comment: '' }); ElMessage.success(approved ? '已通过' : '已驳回'); await load() } catch { ElMessage.error('操作失败') }
  }

  async function handleInstallAgent(id: string) {
    try { await http.post(`/api/v1/agents/${id}/install`); ElMessage.success('已安装'); await load() } catch { ElMessage.error('安装失败') }
  }

  async function handleUninstallAgent(id: string) {
    try { await http.delete(`/api/v1/agents/${id}/uninstall`); ElMessage.success('已卸载'); await load() } catch { ElMessage.error('卸载失败') }
  }

  function isOwner(agent: AgentItem): boolean {
    return !!currentUserId.value && String(agent.user_id) === currentUserId.value
  }

  const statusLabel: Record<string, string> = { draft: '草稿', pending: '审核中', approved: '已通过', rejected: '已驳回' }

  onMounted(() => { void load() })

  return {
    loading, filteredAgents, filterScope, applyFilter, isAdmin, currentUserId,
    dialogVisible, viewDialogVisible, viewAgent, dialogTitle, editingId, saving, form, models, skills,
    openCreate, openEdit, openView, handleSave, handleDelete, handleClone, handleSetDefault,
    handleSubmit, handleWithdraw, handleReview, handleInstallAgent, handleUninstallAgent, isOwner, statusLabel,
  }
}
