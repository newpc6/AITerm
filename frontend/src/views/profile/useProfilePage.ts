import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { getAuthStatus, updateMyProfile } from '@/api/aiterm'
import { clearAuthToken } from '@/auth'
import type { UserItem } from '@/types/api'

export function useProfilePage() {
  const router = useRouter()
  const loading = ref(false)
  const saving = ref(false)
  const user = ref<UserItem | null>(null)
  const displayName = ref('')
  const passwordDialogVisible = ref(false)
  const passwordSaving = ref(false)
  const passwordErrorMessage = ref('')
  const passwordForm = ref({
    current_password: '',
    new_password: '',
    confirm_password: '',
  })

  async function loadProfile() {
    loading.value = true
    try {
      const status = await getAuthStatus()
      user.value = status.user ?? null
      displayName.value = user.value?.display_name || ''
    } catch {
      ElMessage.error('加载用户信息失败')
    } finally {
      loading.value = false
    }
  }

  async function saveDisplayName() {
    if (!displayName.value.trim()) return
    saving.value = true
    try {
      await updateMyProfile({ display_name: displayName.value.trim() })
      ElMessage.success('显示名已更新')
    } catch {
      ElMessage.error('更新失败')
    } finally {
      saving.value = false
    }
  }

  function openPasswordDialog() {
    passwordForm.value = { current_password: '', new_password: '', confirm_password: '' }
    passwordErrorMessage.value = ''
    passwordDialogVisible.value = true
  }

  async function submitPasswordChange() {
    if (passwordSaving.value) return
    if (!passwordForm.value.current_password || !passwordForm.value.new_password) {
      passwordErrorMessage.value = '请完整填写当前密码和新密码。'
      return
    }
    if (passwordForm.value.new_password.length < 8) {
      passwordErrorMessage.value = '新密码至少需要 8 位。'
      return
    }
    if (passwordForm.value.new_password !== passwordForm.value.confirm_password) {
      passwordErrorMessage.value = '两次输入的新密码不一致。'
      return
    }
    passwordSaving.value = true
    passwordErrorMessage.value = ''
    try {
      const { changeMyPassword } = await import('@/api/aiterm')
      await changeMyPassword({
        current_password: passwordForm.value.current_password,
        new_password: passwordForm.value.new_password,
      })
      ElMessage.success('密码修改成功，请重新登录。')
      passwordDialogVisible.value = false
      clearAuthToken()
      router.replace('/login')
    } catch {
      passwordErrorMessage.value = '修改密码失败，请检查当前密码是否正确。'
    } finally {
      passwordSaving.value = false
    }
  }

  onMounted(() => { void loadProfile() })

  return {
    loading, saving, user, displayName,
    passwordDialogVisible, passwordSaving, passwordErrorMessage, passwordForm,
    loadProfile, saveDisplayName, openPasswordDialog, submitPasswordChange,
  }
}
