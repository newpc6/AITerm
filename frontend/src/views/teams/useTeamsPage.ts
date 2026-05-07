import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { http } from '@/api/http'
import type { ApiResponse } from '@/types/api'

interface TeamItem { id: string; name: string; description: string; owner_name: string; member_count: number; created_at: string }
interface TeamMember { id: string; user_id: string; username: string; display_name: string; role: string }

export function useTeamsPage() {
  const loading = ref(false)
  const teams = ref<TeamItem[]>([])
  const dialogVisible = ref(false)
  const editingId = ref<string | null>(null)
  const saving = ref(false)
  const form = ref({ name: '', description: '' })
  const memberDialogVisible = ref(false)
  const memberTeamId = ref('')
  const members = ref<TeamMember[]>([])
  const memberLoading = ref(false)
  const addUserForm = ref({ user_id: '', role: 'member' })

  async function load() {
    loading.value = true
    try { const { data } = await http.get<ApiResponse<TeamItem[]>>('/api/v1/teams'); teams.value = data.data || [] } catch { ElMessage.error('加载失败') }
    finally { loading.value = false }
  }

  function openCreate() { editingId.value = null; form.value = { name: '', description: '' }; dialogVisible.value = true }
  function openEdit(t: TeamItem) { editingId.value = t.id; form.value = { name: t.name, description: t.description }; dialogVisible.value = true }

  async function handleSave() {
    if (!form.value.name.trim()) return
    saving.value = true
    try {
      if (editingId.value) { await http.put(`/api/v1/teams/${editingId.value}`, form.value); ElMessage.success('更新成功') }
      else { await http.post('/api/v1/teams', form.value); ElMessage.success('创建成功') }
      dialogVisible.value = false; await load()
    } catch { ElMessage.error('保存失败') }
    finally { saving.value = false }
  }

  async function handleDelete(id: string) { try { await ElMessageBox.confirm('确定删除？', '删除确认', { type: 'warning' }); await http.delete(`/api/v1/teams/${id}`); ElMessage.success('已删除'); await load() } catch { /* */ } }

  async function showMembers(teamId: string) { memberLoading.value = true; memberTeamId.value = teamId; memberDialogVisible.value = true; try { const { data } = await http.get<ApiResponse<TeamMember[]>>(`/api/v1/teams/${teamId}/members`); members.value = data.data || [] } catch { members.value = [] } finally { memberLoading.value = false } }

  async function addMember() { try { await http.post(`/api/v1/teams/${memberTeamId.value}/members`, addUserForm.value); ElMessage.success('已添加'); await showMembers(memberTeamId.value); addUserForm.value = { user_id: '', role: 'member' } } catch { ElMessage.error('添加失败') } }

  async function removeMember(userId: string) { try { await http.delete(`/api/v1/teams/${memberTeamId.value}/members/${userId}`); ElMessage.success('已移除'); await showMembers(memberTeamId.value) } catch { ElMessage.error('移除失败') } }

  onMounted(() => { void load() })

  return { loading, teams, dialogVisible, editingId, saving, form, memberDialogVisible, memberTeamId, members, memberLoading, addUserForm, load, openCreate, openEdit, handleSave, handleDelete, showMembers, addMember, removeMember }
}
