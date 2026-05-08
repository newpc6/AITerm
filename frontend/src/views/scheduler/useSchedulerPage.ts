import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { http } from '@/api/http'
import { getAgents, getCurrentUser } from '@/api/aiterm'
import type { ApiResponse, AgentItem } from '@/types/api'

interface TaskItem {
  id: string
  user_id: string
  username: string
  name: string
  description: string
  agent_name: string
  cron_expression: string
  enabled: boolean
  last_run_at?: string
  last_result?: string
  next_run_at?: string
}
interface TaskLog {
  id: string
  status: string
  output: string
  error: string
  started_at: string
}

const CRON_PRESETS = [
  { label: '每分钟', value: '* * * * *' },
  { label: '每5分钟', value: '*/5 * * * *' },
  { label: '每小时', value: '0 * * * *' },
  { label: '每天上午8点', value: '0 8 * * *' },
  { label: '每天中午12点', value: '0 12 * * *' },
  { label: '工作日每天上午9点', value: '0 9 * * 1-5' },
  { label: '每周一上午8点', value: '0 8 * * 1' },
  { label: '每月1号上午8点', value: '0 8 1 * *' },
  { label: '每小时第30分', value: '30 * * * *' },
  { label: '每30分钟', value: '*/30 * * * *' },
  { label: '每天两次（8点/20点）', value: '0 8,20 * * *' },
]

export function useSchedulerPage() {
  const loading = ref(false)
  const tasks = ref<TaskItem[]>([])
  const agents = ref<AgentItem[]>([])
  const isAdmin = ref(false)

  const dialogVisible = ref(false)
  const editingId = ref<string | null>(null)
  const saving = ref(false)
  const form = ref({ name: '', description: '', agent_id: '', input_message: '', cron_expression: '0 8 * * *', max_retries: 0, timeout_seconds: 300 })

  const logDialogVisible = ref(false)
  const logs = ref<TaskLog[]>([])
  const logLoading = ref(false)

  async function load() {
    loading.value = true
    try {
      const { data } = await http.get<ApiResponse<TaskItem[]>>('/api/v1/scheduler')
      tasks.value = data.data || []
      try {
        agents.value = await getAgents()
      } catch {
        agents.value = []
      }
      try {
        const u = await getCurrentUser()
        isAdmin.value = u.role === 'admin'
      } catch {
        isAdmin.value = false
      }
    } catch {
      ElMessage.error('加载失败')
    } finally {
      loading.value = false
    }
  }

  function openCreate() {
    editingId.value = null
    form.value = { name: '', description: '', agent_id: agents.value[0]?.id || '', input_message: '', cron_expression: '0 8 * * *', max_retries: 0, timeout_seconds: 300 }
    dialogVisible.value = true
  }

  function openEdit(t: TaskItem) {
    editingId.value = t.id
    form.value = { name: t.name, description: t.description, agent_id: '', input_message: '', cron_expression: t.cron_expression, max_retries: 0, timeout_seconds: 300 }
    dialogVisible.value = true
  }

  function applyCronPreset(val: string) {
    form.value.cron_expression = val
  }

  async function handleSave() {
    if (!form.value.name.trim() || !form.value.input_message.trim()) return
    saving.value = true
    try {
      if (editingId.value) {
        await http.put(`/api/v1/scheduler/${editingId.value}`, form.value)
        ElMessage.success('更新成功')
      } else {
        await http.post('/api/v1/scheduler', form.value)
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
      await http.delete(`/api/v1/scheduler/${id}`)
      ElMessage.success('已删除')
      await load()
    } catch {
      /* */
    }
  }

  async function handleRun(id: string) {
    try {
      await http.post(`/api/v1/scheduler/${id}/run`)
      ElMessage.success('已触发执行')
    } catch {
      ElMessage.error('执行失败')
    }
  }

  async function handleToggle(task: TaskItem) {
    try {
      const { data } = await http.post(`/api/v1/scheduler/${task.id}/toggle`)
      task.enabled = (data as any).data?.enabled ?? !task.enabled
      ElMessage.success(task.enabled ? '已启用' : '已禁用')
    } catch {
      ElMessage.error('操作失败')
    }
  }

  async function showLogs(taskId: string) {
    logLoading.value = true
    logDialogVisible.value = true
    try {
      const { data } = await http.get<ApiResponse<TaskLog[]>>(`/api/v1/scheduler/${taskId}/logs`)
      logs.value = data.data || []
    } catch {
      logs.value = []
    } finally {
      logLoading.value = false
    }
  }

  onMounted(() => {
    void load()
  })

  return {
    loading,
    tasks,
    agents,
    isAdmin,
    dialogVisible,
    editingId,
    saving,
    form,
    logDialogVisible,
    logs,
    logLoading,
    load,
    openCreate,
    openEdit,
    handleSave,
    handleDelete,
    handleRun,
    handleToggle,
    showLogs,
    CRON_PRESETS,
    applyCronPreset,
  }
}
