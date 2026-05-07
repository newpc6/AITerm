import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getSharePreview, verifyShare, type ShareDetailData } from '@/api/aiterm'
import type { ChatMessage } from '@/types/chat'

function createMessageFromApi(item: { id: string; role: string; content: string; type?: string; created_at: string | null }): ChatMessage {
  let content = item.content
  let metadata: Record<string, unknown> | undefined = undefined

  try {
    const parsed = JSON.parse(item.content)
    if (typeof parsed === 'object' && parsed !== null) {
      if (typeof parsed.answer === 'string') {
        content = parsed.answer
        metadata = {
          thinking: parsed.thinking,
          reasoning_duration: parsed.reasoning_duration,
          total_duration: parsed.total_duration,
          tool_calls: parsed.tool_calls,
          iterations: parsed.iterations,
          full_input: parsed.full_input,
          usage: parsed.usage,
        }
      } else if (typeof parsed.message === 'string') {
        content = parsed.message
        const { message, ...rest } = parsed
        if (Object.keys(rest).length > 0) {
          metadata = rest
        }
      }
    }
  } catch {
    // JSON parse failed, use raw content
  }

  return {
    id: item.id,
    role: item.role as ChatMessage['role'],
    content,
    type: item.type as ChatMessage['type'],
    metadata,
    createdAt: item.created_at || new Date().toISOString(),
  }
}

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
    return shareData.value.messages.map((msg) =>
      createMessageFromApi({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        type: msg.type,
        created_at: msg.created_at,
      }),
    )
  })

  const actionableMessageIds = computed(() => {
    return messages.value.filter((msg) => msg.content).map((msg) => msg.id)
  })

  const displaySettings = computed(() => ({
    showThinking: shareData.value?.show_thinking ?? true,
    expandThinking: true,
    showTools: shareData.value?.show_tools ?? true,
    expandTools: true,
    showInput: shareData.value?.show_input ?? true,
    expandInput: true,
    showFullInput: shareData.value?.show_full_input ?? false,
    expandFullInput: true,
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

    const textToCopy = message.content

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
