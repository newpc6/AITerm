import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { http } from '@/api/http'
import { getMyTools, getCurrentUser } from '@/api/aiterm'
import type { ApiResponse } from '@/types/api'
import type { UserTool } from '@/types/tool'

interface SkillItem {
  id: string
  user_id: string
  name: string
  display_name: string
  description: string
  version: string
  category: string
  system_prompt: string
  tool_names: string[]
  status: string
  review_comment: string
  is_public: boolean
  is_default: boolean
  installed: boolean
  created_at: string
  updated_at: string
}

export function useSkillsPage() {
  const loading = ref(false)
  const skills = ref<SkillItem[]>([])
  const scope = ref('my')
  const tools = ref<UserTool[]>([])
  const currentUserId = ref('')
  const isAdmin = ref(false)

  const dialogVisible = ref(false)
  const viewDialogVisible = ref(false)
  const viewSkill = ref<SkillItem | null>(null)
  const dialogTitle = ref('新建技能')
  const editingId = ref<string | null>(null)
  const saving = ref(false)
  const form = ref({ name: '', display_name: '', description: '', category: 'custom', system_prompt: '', tool_names: [] as string[] })

  async function load() {
    loading.value = true
    try {
      const { data } = await http.get<ApiResponse<SkillItem[]>>('/api/v1/skills', { params: { scope: scope.value } })
      skills.value = data.data || []
      tools.value = await getMyTools()
      try {
        const u = await getCurrentUser()
        currentUserId.value = u.id
        isAdmin.value = u.role === 'admin'
      } catch {
        currentUserId.value = ''
      }
    } catch {
      ElMessage.error('加载失败')
    } finally {
      loading.value = false
    }
  }

  function openCreate() {
    editingId.value = null
    dialogTitle.value = '新建技能'
    form.value = { name: '', display_name: '', description: '', category: 'custom', system_prompt: '', tool_names: [] }
    dialogVisible.value = true
  }

  function openEdit(s: SkillItem) {
    editingId.value = s.id
    dialogTitle.value = '编辑技能'
    form.value = { name: s.name, display_name: s.display_name, description: s.description, category: s.category, system_prompt: s.system_prompt, tool_names: [...(s.tool_names || [])] }
    dialogVisible.value = true
  }

  function openView(s: SkillItem) {
    viewSkill.value = s
    viewDialogVisible.value = true
  }

  async function handleSave() {
    if (!form.value.name.trim()) return
    saving.value = true
    try {
      const payload = { ...form.value }
      if (editingId.value) {
        await http.put(`/api/v1/skills/${editingId.value}`, payload)
        ElMessage.success('更新成功')
      } else {
        await http.post('/api/v1/skills', payload)
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
      await ElMessageBox.confirm('确定删除吗？', '删除确认', { type: 'warning' })
      await http.delete(`/api/v1/skills/${id}`)
      ElMessage.success('已删除')
      await load()
    } catch {
      /* cancelled */
    }
  }

  async function handleSubmit(id: string) {
    try {
      await http.post(`/api/v1/skills/${id}/submit`)
      ElMessage.success('已提交审核')
      await load()
    } catch {
      ElMessage.error('提交失败')
    }
  }

  async function handleWithdraw(id: string) {
    try {
      await http.post(`/api/v1/skills/${id}/withdraw`)
      ElMessage.success('已撤回')
      await load()
    } catch {
      ElMessage.error('撤回失败')
    }
  }

  async function handleReview(id: string, approved: boolean) {
    try {
      await http.post(`/api/v1/skills/${id}/review`, { approved, comment: '' })
      ElMessage.success(approved ? '已通过' : '已驳回')
      await load()
    } catch {
      ElMessage.error('操作失败')
    }
  }

  async function handleInstall(id: string) {
    try {
      await http.post(`/api/v1/skills/${id}/install`)
      ElMessage.success('已安装')
      await load()
    } catch {
      ElMessage.error('安装失败')
    }
  }

  async function handleUninstall(id: string) {
    try {
      await http.delete(`/api/v1/skills/${id}/uninstall`)
      ElMessage.success('已卸载')
      await load()
    } catch {
      ElMessage.error('卸载失败')
    }
  }

  function isOwner(s: SkillItem): boolean {
    return !!currentUserId.value && String(s.user_id) === currentUserId.value
  }

  const statusLabel: Record<string, string> = { draft: '草稿', pending: '审核中', approved: '已通过', rejected: '已驳回' }

  onMounted(() => {
    void load()
  })

  return {
    loading,
    skills,
    scope,
    load,
    tools,
    currentUserId,
    isAdmin,
    dialogVisible,
    viewDialogVisible,
    viewSkill,
    dialogTitle,
    editingId,
    saving,
    form,
    openCreate,
    openEdit,
    openView,
    handleSave,
    handleDelete,
    handleSubmit,
    handleWithdraw,
    handleReview,
    handleInstall,
    handleUninstall,
    isOwner,
    statusLabel,
  }
}
