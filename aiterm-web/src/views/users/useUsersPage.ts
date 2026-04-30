import { computed, onMounted, ref } from 'vue'
import { ElMessageBox } from 'element-plus'

import { createUser, deleteUser, getUsers, resetUserPassword, updateUser } from '@/api/aiterm'
import type { UserItem, UserPayload } from '@/types/api'

function createDefaultForm(): UserPayload {
  return {
    username: '',
    display_name: '',
    password: '',
    role: 'user',
    status: 'active',
  }
}

export function useUsersPage() {
  const loading = ref(false)
  const saving = ref(false)
  const errorMessage = ref('')
  const successMessage = ref('')
  const users = ref<UserItem[]>([])
  const form = ref<UserPayload>(createDefaultForm())
  const editingUser = ref<UserItem | null>(null)
  const dialogVisible = ref(false)
  const page = ref(1)
  const pageSize = ref(10)
  const total = ref(0)

  async function loadUsers() {
    loading.value = true
    errorMessage.value = ''

    try {
      const data = await getUsers({ page: page.value, page_size: pageSize.value })
      users.value = data.items
      total.value = data.total
    } catch {
      errorMessage.value = '用户接口不可用。'
    } finally {
      loading.value = false
    }
  }

  function handlePageChange(newPage: number) {
    page.value = newPage
    void loadUsers()
  }

  function handlePageSizeChange(newSize: number) {
    pageSize.value = newSize
    page.value = 1
    void loadUsers()
  }

  function syncFormFromUser(user: UserItem) {
    form.value = {
      username: user.username,
      display_name: user.display_name,
      password: '',
      role: user.role,
      status: user.status,
    }
  }

  function startCreateUser() {
    editingUser.value = null
    form.value = createDefaultForm()
    successMessage.value = ''
    errorMessage.value = ''
    dialogVisible.value = true
  }

  function startEditUser(user: UserItem) {
    editingUser.value = user
    syncFormFromUser(user)
    successMessage.value = ''
    errorMessage.value = ''
    dialogVisible.value = true
  }

  function closeDialog() {
    dialogVisible.value = false
    editingUser.value = null
    form.value = createDefaultForm()
    successMessage.value = ''
    errorMessage.value = ''
  }

  async function saveUser() {
    saving.value = true
    errorMessage.value = ''
    successMessage.value = ''

    try {
      if (editingUser.value) {
        const updated = await updateUser(editingUser.value.id, {
          display_name: form.value.display_name,
          role: form.value.role,
          status: form.value.status,
        })
        successMessage.value = '用户更新成功。'
        editingUser.value = updated
      } else {
        await createUser(form.value)
        successMessage.value = '用户创建成功。'
      }
      closeDialog()
      await loadUsers()
    } catch {
      errorMessage.value = editingUser.value ? '更新用户失败，请确认不是在禁用或降级最后一个管理员。' : '创建用户失败，请检查用户名是否重复。'
    } finally {
      saving.value = false
    }
  }

  async function removeUser(user: UserItem) {
    errorMessage.value = ''
    successMessage.value = ''

    try {
      await ElMessageBox.confirm(`确定删除用户 ${user.username} 吗？`, '删除用户', {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
      })
    } catch {
      return
    }

    loading.value = true
    try {
      await deleteUser(user.id)
      successMessage.value = '用户删除成功。'
      total.value = Math.max(0, total.value - 1)
      if (users.value.length === 0 && page.value > 1) {
        page.value -= 1
      }
      await loadUsers()
    } catch {
      errorMessage.value = '删除用户失败，请避免删除当前登录用户或最后一个管理员。'
    } finally {
      loading.value = false
    }
  }

  async function resetPassword(user: UserItem) {
    errorMessage.value = ''
    successMessage.value = ''

    let password = ''
    try {
      const result = await ElMessageBox.prompt(`请输入用户 ${user.username} 的新密码`, '重置密码', {
        inputType: 'password',
        inputPlaceholder: '至少 8 位',
        confirmButtonText: '保存',
        cancelButtonText: '取消',
        inputValidator: (value) => {
          if (!value || value.length < 8) {
            return '密码至少需要 8 位'
          }
          return true
        },
      })
      password = result.value
    } catch {
      return
    }

    loading.value = true
    try {
      await resetUserPassword(user.id, { password })
      successMessage.value = '密码重置成功。'
    } catch {
      errorMessage.value = '密码重置失败。'
    } finally {
      loading.value = false
    }
  }

  const userCount = computed(() => total.value)
  const isEditing = computed(() => !!editingUser.value)
  const dialogTitle = computed(() => (editingUser.value ? '编辑用户' : '新建用户'))

  onMounted(() => {
    void loadUsers()
  })

  return {
    closeDialog,
    dialogTitle,
    dialogVisible,
    editingUser,
    errorMessage,
    form,
    isEditing,
    loading,
    loadUsers,
    removeUser,
    resetPassword,
    saving,
    startCreateUser,
    startEditUser,
    successMessage,
    saveUser,
    userCount,
    users,
    page,
    pageSize,
    total,
    handlePageChange,
    handlePageSizeChange,
  }
}
