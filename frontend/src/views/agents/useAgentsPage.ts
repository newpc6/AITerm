import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getAgents, createAgent, updateAgent, deleteAgent, cloneAgent, setDefaultAgent, getModels } from '@/api/aiterm'
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
  const filterScope = ref<string>('my')

  const dialogVisible = ref(false)
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
      try {
        models.value = ((await getModels()) as { items: ModelConfigItem[] }).items || []
      } catch {
        models.value = []
      }
      try {
        const { data } = await http.get('/api/v1/skills/installed/list')
        skills.value = (data as any).data || []
      } catch {
        skills.value = []
      }
    } catch {
      ElMessage.error('加载失败')
    } finally {
      loading.value = false
      applyFilter()
    }
  }

  function applyFilter() {
    if (filterScope.value === 'my') {
      filteredAgents.value = agents.value.filter((a) => a.scope === 'private')
    } else if (filterScope.value === 'template') {
      filteredAgents.value = agents.value.filter((a) => a.is_template)
    } else if (filterScope.value === 'public') {
      filteredAgents.value = agents.value.filter((a) => a.is_public)
    } else {
      filteredAgents.value = agents.value
    }
  }

  function openCreate() {
    editingId.value = null
    dialogTitle.value = '新建智能体'
    form.value = {
      name: '',
      description: '',
      icon: 'robot',
      model_id: models.value[0]?.id || '',
      skill_ids: [],
      system_prompt: '',
      temperature: 0.7,
      max_iterations: 10,
      is_public: false,
      is_template: false,
      scope: 'private',
    }
    dialogVisible.value = true
  }

  function openEdit(agent: AgentItem) {
    editingId.value = agent.id
    dialogTitle.value = '编辑智能体'
    form.value = {
      name: agent.name,
      description: agent.description,
      icon: agent.icon,
      model_id: agent.model_id || '',
      skill_ids: agent.skill_ids || [],
      system_prompt: agent.system_prompt,
      temperature: agent.temperature,
      max_iterations: agent.max_iterations,
      is_public: agent.is_public,
      is_template: agent.is_template,
      scope: agent.scope,
    }
    dialogVisible.value = true
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
      dialogVisible.value = false
      await load()
    } catch {
      ElMessage.error('保存失败')
    } finally {
      saving.value = false
    }
  }

  async function handleDelete(id: string) {
    try {
      await ElMessageBox.confirm('确定删除该智能体吗？', '删除确认', { type: 'warning' })
      await deleteAgent(id)
      ElMessage.success('已删除')
      await load()
    } catch {
      /* cancelled */
    }
  }

  async function handleClone(id: string) {
    try {
      await cloneAgent(id)
      ElMessage.success('已克隆')
      await load()
    } catch {
      ElMessage.error('克隆失败')
    }
  }

  async function handleSetDefault(id: string) {
    try {
      await setDefaultAgent(id)
      ElMessage.success('已设为默认')
      await load()
    } catch {
      ElMessage.error('设置失败')
    }
  }

  onMounted(() => {
    void load()
  })

  return {
    loading,
    filteredAgents,
    filterScope,
    applyFilter,
    dialogVisible,
    dialogTitle,
    editingId,
    saving,
    form,
    models,
    skills,
    openCreate,
    openEdit,
    handleSave,
    handleDelete,
    handleClone,
    handleSetDefault,
  }
}
