import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { deleteChat, getChats } from '@/api/aiterm'
import type { ChatItem } from '@/types/api'

export function useConversationHistoryPage() {
  const router = useRouter()
  const loading = ref(false)
  const deletingChatId = ref('')
  const errorMessage = ref('')
  const items = ref<ChatItem[]>([])
  const page = ref(1)
  const pageSize = ref(20)
  const total = ref(0)

  async function loadConversations() {
    loading.value = true
    errorMessage.value = ''

    try {
      const data = await getChats({ page: page.value, page_size: pageSize.value })
      items.value = data.items
      total.value = data.total
    } catch {
      errorMessage.value = '历史会话接口不可用。'
    } finally {
      loading.value = false
    }
  }

  function handlePageChange(newPage: number) {
    page.value = newPage
    void loadConversations()
  }

  function handlePageSizeChange(newSize: number) {
    pageSize.value = newSize
    page.value = 1
    void loadConversations()
  }

  function openConversation(chatId: string) {
    void router.push({
      path: '/chat',
      query: {
        chat_id: chatId,
      },
    })
  }

  async function removeConversation(chatId: string) {
    try {
      await ElMessageBox.confirm('删除后将一并移除该会话下的历史消息和关联任务，是否继续？', '删除会话', {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      })
    } catch {
      return
    }

    deletingChatId.value = chatId
    errorMessage.value = ''

    try {
      await deleteChat(chatId)
      items.value = items.value.filter((item) => item.id !== chatId)
      total.value = Math.max(0, total.value - 1)
      ElMessage.success('会话已删除。')
      if (items.value.length === 0 && page.value > 1) {
        page.value -= 1
        void loadConversations()
      }
    } catch {
      errorMessage.value = '删除会话失败。'
    } finally {
      deletingChatId.value = ''
    }
  }

  onMounted(() => {
    void loadConversations()
  })

  return {
    errorMessage,
    deletingChatId,
    items,
    loadConversations,
    loading,
    removeConversation,
    openConversation,
    page,
    pageSize,
    total,
    handlePageChange,
    handlePageSizeChange,
  }
}
