import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getSharePreview, verifyShare, type ShareDetailData } from '@/api/aiterm'
import type { ChatMessage } from '@/types/chat'

export function useSharePage() {
  const route = useRoute()
  const router = useRouter()

  const loading = ref(true)
  const error = ref('')
  const shareData = ref<ShareDetailData | null>(null)
  const showPasswordForm = ref(false)
  const password = ref('')
  const passwordError = ref('')
  const verifying = ref(false)

  const shareId = computed(() => route.params.shareId as string)

  const messages = computed<ChatMessage[]>(() => {
    if (!shareData.value?.messages) return []
    return shareData.value.messages.map((msg) => {
      return {
        id: msg.id,
        role: msg.role as 'user' | 'assistant',
        content: msg.content,
        type: msg.type as ChatMessage['type'],
        createdAt: msg.created_at || new Date().toISOString(),
      }
    })
  })

  const actionableMessageIds = computed(() => {
    return messages.value.filter((msg) => msg.role === 'assistant' && msg.content).map((msg) => msg.id)
  })

  const displaySettings = computed(() => ({
    showThinking: shareData.value?.show_thinking ?? true,
    expandThinking: true,
    showTools: shareData.value?.show_tools ?? true,
    expandTools: true,
    showInput: shareData.value?.show_input ?? true,
    expandInput: true,
    autoCollapse: false,
  }))

  async function loadShare() {
    if (!shareId.value) {
      error.value = '无效的分享链接'
      loading.value = false
      return
    }

    try {
      const preview = await getSharePreview(shareId.value)
      if (preview.has_password) {
        showPasswordForm.value = true
      } else {
        const data = await verifyShare(shareId.value, { share_id: shareId.value })
        shareData.value = data
      }
    } catch (e: unknown) {
      const err = e as { response?: { data?: { code?: number; message?: string } } }
      if (err?.response?.data?.code === 4100) {
        error.value = '此分享链接已过期'
      } else if (err?.response?.data?.code === 4040) {
        error.value = '分享链接不存在'
      } else {
        error.value = err?.response?.data?.message || '加载失败'
      }
    } finally {
      loading.value = false
    }
  }

  async function handleVerifyPassword() {
    if (!password.value.trim()) {
      passwordError.value = '请输入密码'
      return
    }

    verifying.value = true
    passwordError.value = ''

    try {
      const data = await verifyShare(shareId.value, {
        share_id: shareId.value,
        password: password.value,
      })
      shareData.value = data
      showPasswordForm.value = false
    } catch (e: unknown) {
      const err = e as { response?: { data?: { message?: string } } }
      passwordError.value = err?.response?.data?.message || '密码错误'
    } finally {
      verifying.value = false
    }
  }

  function formatDate(dateStr: string | null) {
    if (!dateStr) return ''
    return new Date(dateStr).toLocaleString()
  }

  function goHome() {
    router.push('/')
  }

  async function copyMessage(messageId: string) {
    const message = messages.value.find((item) => item.id === messageId)
    if (!message) {
      return
    }

    let textToCopy = message.content
    if (message.role === 'assistant') {
      try {
        const parsed = JSON.parse(message.content)
        if (typeof parsed === 'object' && parsed !== null && typeof parsed.answer === 'string') {
          textToCopy = parsed.answer
        }
      } catch {
        // Not JSON, use as-is
      }
    }

    try {
      await navigator.clipboard.writeText(textToCopy)
      ElMessage.success('已复制')
    } catch {
      const textarea = document.createElement('textarea')
      textarea.value = textToCopy
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.select()
      try {
        document.execCommand('copy')
        ElMessage.success('已复制')
      } catch {
        ElMessage.error('复制失败')
      }
      document.body.removeChild(textarea)
    }
  }

  onMounted(() => {
    loadShare()
  })

  return {
    loading,
    error,
    shareData,
    showPasswordForm,
    password,
    passwordError,
    verifying,
    messages,
    actionableMessageIds,
    displaySettings,
    handleVerifyPassword,
    formatDate,
    goHome,
    copyMessage,
  }
}
