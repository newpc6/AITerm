import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { getAuthToken, setAuthToken } from '@/auth'
import { getAuthStatus, login } from '@/api/aiterm'

export function useLoginPage() {
  const router = useRouter()
  const loading = ref(false)
  const submitting = ref(false)
  const errorMessage = ref('')
  const form = ref({
    username: 'admin',
    password: '12345678',
  })

  async function loadStatus() {
    loading.value = true
    errorMessage.value = ''

    try {
      const status = await getAuthStatus()
      if (status.authenticated && getAuthToken()) {
        void router.replace('/chat')
      }
    } catch {
      errorMessage.value = '登录状态接口不可用。'
    } finally {
      loading.value = false
    }
  }

  async function submitLogin() {
    submitting.value = true
    errorMessage.value = ''

    try {
      const data = await login(form.value)
      setAuthToken(data.token)
      void router.replace('/chat')
    } catch {
      errorMessage.value = '登录失败，请检查用户名或密码。'
    } finally {
      submitting.value = false
    }
  }

  onMounted(() => {
    void loadStatus()
  })

  return {
    errorMessage,
    form,
    loading,
    submitLogin,
    submitting,
  }
}
