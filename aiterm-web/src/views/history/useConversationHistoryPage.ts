import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { deleteConversation, getConversations } from '@/api/aiterm'
import type { ConversationListItem } from '@/types/api'

export function useConversationHistoryPage() {
  const router = useRouter()
  const loading = ref(false)
  const deletingConversationId = ref('')
  const errorMessage = ref('')
  const items = ref<ConversationListItem[]>([])

  async function loadConversations() {
    loading.value = true
    errorMessage.value = ''

    try {
      const data = await getConversations()
      items.value = data.items
    } catch {
      errorMessage.value = '历史会话接口不可用。'
    } finally {
      loading.value = false
    }
  }

  function openConversation(conversationId: string) {
    void router.push({
      path: '/chat',
      query: {
        conversation_id: conversationId,
      },
    })
  }

  async function removeConversation(conversationId: string) {
    try {
      await ElMessageBox.confirm('删除后将一并移除该会话下的历史消息和关联任务，是否继续？', '删除会话', {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      })
    } catch {
      return
    }

    deletingConversationId.value = conversationId
    errorMessage.value = ''

    try {
      await deleteConversation(conversationId)
      items.value = items.value.filter((item) => item.id !== conversationId)
      ElMessage.success('会话已删除。')
    } catch {
      errorMessage.value = '删除会话失败。'
    } finally {
      deletingConversationId.value = ''
    }
  }

  onMounted(() => {
    void loadConversations()
  })

  return {
    errorMessage,
    deletingConversationId,
    items,
    loadConversations,
    loading,
    removeConversation,
    openConversation,
  }
}
