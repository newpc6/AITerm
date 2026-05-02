import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { getAuthToken } from '@/auth'
import { buildTaskContinueUrl, confirmTask, deleteChat, getAuthStatus, getChatMessages, getChats, getModels, getNodes, provideTaskInput, restartTask, stopTask, streamChat } from '@/api/aiterm'
import { getApiBaseUrl } from '@/config'
import { formatDateTime } from '@/utils/datetime'
import type { ChatItem, ModelConfigItem, NodeItem, TaskItem, TaskStreamOutputData, TaskStreamStatusData } from '@/types/api'
import type { ChatMessage } from '@/types/chat'

const LAST_CONVERSATION_ID_KEY = 'aiterm:last-conversation-id'
type SidebarGroup<T> = {
  key: string
  label: string
  items: T[]
}

type TaskOutputKind = 'stdout' | 'stderr' | 'plan' | 'plan.info' | 'approval' | 'step.start' | 'step.result' | 'repair.analysis' | 'repair.retry' | 'repair.stop' | 'summary' | 'input.request'

let localMessageCounter = 0

function createLocalMessage(role: ChatMessage['role'], content: string, createdAt = new Date().toISOString()): ChatMessage {
  localMessageCounter += 1
  return {
    id: `local-${Date.now()}-${localMessageCounter}`,
    role,
    content,
    createdAt,
  }
}

function createMessageFromApi(item: { id: string; role: ChatMessage['role']; content: string; type?: string; metadata?: Record<string, unknown>; created_at: string }): ChatMessage {
  return {
    id: item.id,
    role: item.role,
    content: item.content,
    type: item.type as ChatMessage['type'],
    metadata: item.metadata,
    createdAt: item.created_at,
  }
}

function buildEventSourceUrl(taskId: string) {
  const baseUrl = getApiBaseUrl().trim()
  const eventPath = `/api/v1/tasks/${taskId}/events`
  const url = baseUrl ? new URL(eventPath, baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`) : new URL(eventPath, window.location.origin)
  const token = getAuthToken()
  if (token) {
    url.searchParams.set('access_token', token)
  }
  return url.toString()
}

function createInitialMessages(): ChatMessage[] {
  return [createLocalMessage('assistant', '已进入对话模式，你可以直接向模型提问，我会按一问一答的方式继续这个会话。')]
}

function shortenLabel(value: string, maxLength: number) {
  const trimmed = value.trim()
  if (!trimmed) {
    return ''
  }

  const runes = Array.from(trimmed)
  if (runes.length <= maxLength) {
    return trimmed
  }

  return `${runes.slice(0, maxLength).join('')}...`
}

function includesKeyword(parts: Array<string | undefined>, keyword: string) {
  if (!keyword) {
    return true
  }
  return parts.some((part) => (part ?? '').toLowerCase().includes(keyword))
}

function parseTimestamp(value: string) {
  const timestamp = Date.parse(value)
  return Number.isNaN(timestamp) ? 0 : timestamp
}

function buildChatGroups(items: ChatItem[], search: string): SidebarGroup<ChatItem>[] {
  const keyword = search.trim().toLowerCase()
  const now = Date.now()
  const dayMs = 24 * 60 * 60 * 1000
  const groups = new Map<string, SidebarGroup<ChatItem>>()

  for (const item of items) {
    if (!includesKeyword([item.title, item.summary, item.id], keyword)) {
      continue
    }

    const age = now - parseTimestamp(item.updated_at || '')
    const key = age <= dayMs ? 'today' : age <= dayMs * 7 ? 'recent' : 'earlier'
    const label = key === 'today' ? '今天' : key === 'recent' ? '近 7 天' : '更早'
    if (!groups.has(key)) {
      groups.set(key, { key, label, items: [] })
    }
    groups.get(key)?.items.push(item)
  }

  return Array.from(groups.values())
}

export function useChatPage() {
  const route = useRoute()
  const router = useRouter()
  const input = ref('')
  const loading = ref(false)
  const confirming = ref(false)
  const chatStreaming = ref(false)
  const taskStreaming = ref(false)
  const errorMessage = ref('')
  const sidebarLoading = ref(false)
  const sidebarSearch = ref('')
  const conversationId = ref('')
  const activeTaskId = ref('')
  const selectedNodeId = ref('')
  const selectedModelId = ref('')
  const availableNodes = ref<NodeItem[]>([])
  const availableModels = ref<ModelConfigItem[]>([])
  const currentUserName = ref('用户')
  const chats = ref<ChatItem[]>([])
  const messages = ref<ChatMessage[]>(createInitialMessages())
  const chatPage = ref(1)
  const chatPageSize = ref(20)
  const chatTotal = ref(0)

  const taskStatus = ref('')
  const taskRiskReason = ref('')
  const inputQuestion = ref('')
  const inputType = ref<'text' | 'select' | 'multiselect'>('text')
  const inputOptions = ref<string[]>([])
  const inputPlaceholder = ref('')
  const waitingForInput = ref(false)
  const waitingForConfirm = ref(false)

  let taskEventSource: EventSource | null = null
  let chatStreamController: AbortController | null = null

  function resetConversationState() {
    closeStreams()
    conversationId.value = ''
    activeTaskId.value = ''
    messages.value = createInitialMessages()
    localStorage.removeItem(LAST_CONVERSATION_ID_KEY)
  }

  function startNewConversation() {
    resetConversationState()
    input.value = ''
    void router.replace({ path: '/chat' })
  }

  function appendAssistantMessage(content: string) {
    messages.value.push(createLocalMessage('assistant', content))
  }

  function formatTaskOutputMessage(stream: string, content: string) {
    const normalized = content.trim()
    if (!normalized) {
      return ''
    }

    switch (stream as TaskOutputKind) {
      case 'stdout':
        return normalized
      case 'stderr':
        return `[错误] ${normalized}`
      case 'plan.info':
        return normalized
      case 'plan':
        return `任务计划如下：\n${normalized}`
      case 'approval':
        return normalized
      case 'input.request':
        return '等待用户输入...'
      case 'step.start':
      case 'step.result':
      case 'repair.analysis':
      case 'repair.retry':
      case 'repair.stop':
      case 'summary':
        return normalized
      default:
        return normalized
    }
  }

  function formatConversationMessage(type: string, content: string) {
    const normalized = content.trim()
    if (!normalized) {
      return ''
    }

    switch (type) {
      case 'error':
        return `[错误] ${normalized}`
      case 'plan':
        return `任务计划如下：\n${normalized}`
      case 'step':
        return normalized
      case 'output':
        return normalized
      case 'approval':
        return ''
      case 'approval_confirmed':
        return normalized
      case 'input':
        return normalized
      case 'analysis':
        return `[分析] ${normalized}`
      case 'retry':
        return `[重试] ${normalized}`
      case 'summary':
        return normalized
      default:
        return normalized
    }
  }

  async function loadChatMessages(targetChatId: string) {
    try {
      const data = await getChatMessages(targetChatId)
      messages.value = data.items.map((item) => createMessageFromApi(item))

      if (messages.value.length === 0) {
        messages.value = createInitialMessages()
      }
    } catch {
      resetConversationState()
      void router.replace({ path: '/chat' })
      errorMessage.value = '该会话不存在或已被删除。'
    }
  }

  async function switchChat(targetChatId: string) {
    if (!targetChatId) {
      return
    }

    closeStreams()
    conversationId.value = targetChatId
    localStorage.setItem(LAST_CONVERSATION_ID_KEY, targetChatId)
    void router.replace({
      path: '/chat',
      query: {
        conversation_id: targetChatId,
      },
    })
    await loadChatMessages(targetChatId)
  }

  async function loadNodes() {
    try {
      const data = await getNodes()
      availableNodes.value = data.items
      if (!selectedNodeId.value && data.items.length > 0) {
        selectedNodeId.value = data.items[0].id
      }
    } catch {
      errorMessage.value = '节点接口不可用。'
    }
  }

  async function loadModels() {
    try {
      const data = await getModels()
      availableModels.value = data.items || []
      const defaultModel = availableModels.value.find((m) => m.is_default)
      if (!selectedModelId.value && defaultModel) {
        selectedModelId.value = defaultModel.id
      } else if (!selectedModelId.value && availableModels.value.length > 0) {
        selectedModelId.value = availableModels.value[0].id
      }
    } catch {
      // Ignore model loading errors
    }
  }

  async function loadViewerMeta() {
    try {
      const status = await getAuthStatus()
      currentUserName.value = status.user?.display_name || status.user?.username || '用户'
    } catch {
      currentUserName.value = '用户'
    }
  }

  async function loadChats(reset = true) {
    try {
      if (reset) {
        chatPage.value = 1
      }
      const data = await getChats({ page: chatPage.value, page_size: chatPageSize.value })
      if (reset) {
        chats.value = data.items
      } else {
        chats.value = [...chats.value, ...data.items]
      }
      chatTotal.value = data.total
    } catch {
      errorMessage.value = '历史会话接口不可用。'
    }
  }

  async function loadMoreChats() {
    if (chats.value.length >= chatTotal.value) {
      return
    }
    chatPage.value += 1
    await loadChats(false)
  }

  async function reloadSidebarData() {
    sidebarLoading.value = true
    try {
      await loadChats()
    } finally {
      sidebarLoading.value = false
    }
  }

  function setSelectedNodeId(value: string) {
    selectedNodeId.value = value
  }

  function setSelectedModelId(value: string) {
    selectedModelId.value = value
  }

  function closeTaskStream() {
    if (taskEventSource) {
      taskEventSource.close()
      taskEventSource = null
    }
    taskStreaming.value = false
  }

  function abortChatStream() {
    if (chatStreamController) {
      chatStreamController.abort()
      chatStreamController = null
    }
    chatStreaming.value = false
  }

  function closeStreams() {
    closeTaskStream()
    abortChatStream()
  }

  function markLastAssistantMessageStopped() {
    const lastMessage = messages.value[messages.value.length - 1]
    if (!lastMessage || lastMessage.role !== 'assistant') {
      messages.value.push(createLocalMessage('assistant', '回答已中止。'))
      return
    }

    if (!lastMessage.content.trim()) {
      lastMessage.content = '回答已中止。'
      return
    }

    if (!lastMessage.content.includes('[回答已中止]')) {
      lastMessage.content = `${lastMessage.content}\n\n[回答已中止]`
    }
  }

  function stopChatResponse() {
    if (!chatStreaming.value) {
      return
    }
    markLastAssistantMessageStopped()
    abortChatStream()
  }

  function findRetrySourceMessage(messageId: string) {
    const index = messages.value.findIndex((item) => item.id === messageId)
    if (index <= 0) {
      return null
    }

    const message = messages.value[index]
    if (message.role !== 'assistant') {
      return null
    }

    for (let cursor = index - 1; cursor >= 0; cursor -= 1) {
      const candidate = messages.value[cursor]
      if (candidate.role === 'user' && candidate.content.trim()) {
        return candidate
      }
    }
    return null
  }

  async function copyMessage(messageId: string) {
    const message = messages.value.find((item) => item.id === messageId)
    if (!message) {
      return
    }

    try {
      await navigator.clipboard.writeText(message.content)
      ElMessage.success('已复制')
    } catch {
      ElMessage.error('复制失败，请检查浏览器权限')
    }
  }

  function connectTaskStream(taskId: string) {
    closeTaskStream()
    activeTaskId.value = taskId
    taskStreaming.value = true
    taskEventSource = new EventSource(buildEventSourceUrl(taskId))

    taskEventSource.addEventListener('conversation.message', (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as { conversation_id: string; type: string; content: string }
      if (payload.type === 'approval') {
        waitingForConfirm.value = true
        taskRiskReason.value = payload.content
      }
      const message = formatConversationMessage(payload.type, payload.content)
      if (message) {
        appendAssistantMessage(message)
      }
    })

    taskEventSource.addEventListener('conversation.input', (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as { conversation_id: string; question: string; input_type: string; options?: string[]; placeholder?: string }
      inputQuestion.value = payload.question
      inputType.value = payload.input_type as 'text' | 'select' | 'multiselect'
      inputOptions.value = payload.options || []
      inputPlaceholder.value = payload.placeholder || ''
      waitingForInput.value = true
    })

    taskEventSource.addEventListener('conversation.done', () => {
      closeTaskStream()
      void reloadSidebarData()
    })

    taskEventSource.onerror = () => {
      closeTaskStream()
      void reloadSidebarData()
    }
  }

  function ensureAssistantPlaceholder() {
    const lastMessage = messages.value[messages.value.length - 1]
    if (lastMessage?.role === 'assistant') {
      return lastMessage
    }

    const placeholder = createLocalMessage('assistant', '')
    messages.value.push(placeholder)
    return placeholder
  }

  function appendAssistantDelta(delta: string) {
    const placeholder = ensureAssistantPlaceholder()
    placeholder.content += delta
  }

  function finalizeAssistantStream(reply: string) {
    const placeholder = ensureAssistantPlaceholder()
    placeholder.content = reply
  }

  async function submitChatMessage(value: string, targetNodeId: string, targetModelId: string) {
    abortChatStream()
    chatStreaming.value = true
    taskStreaming.value = false
    const controller = new AbortController()
    chatStreamController = controller

    try {
      await streamChat(
        {
          node_id: targetNodeId,
          model_id: targetModelId || undefined,
          message: value,
        },
        {
          onMeta: (data) => {
            conversationId.value = data.conversation_id
            if ((data as { mode?: string }).mode === 'task') {
              taskStreaming.value = true
            }
            localStorage.setItem(LAST_CONVERSATION_ID_KEY, data.conversation_id)
            void router.replace({
              path: '/chat',
              query: {
                conversation_id: data.conversation_id,
              },
            })
          },
          onDelta: (data) => {
            if (!conversationId.value) {
              conversationId.value = data.conversation_id
            }
            appendAssistantDelta(data.delta)
          },
          onDone: (data) => {
            conversationId.value = data.conversation_id
            finalizeAssistantStream(data.reply)
          },
          onTaskCreated: (data) => {
            activeTaskId.value = data.task_id
          },
          onConversationMessage: (data) => {
            if (data.type === 'approval') {
              waitingForConfirm.value = true
              taskRiskReason.value = data.content
            }
            const message = formatConversationMessage(data.type, data.content)
            if (message) {
              appendAssistantMessage(message)
            }
          },
          onConversationInput: (data) => {
            inputQuestion.value = data.question
            inputType.value = data.input_type as 'text' | 'select' | 'multiselect'
            inputOptions.value = data.options || []
            inputPlaceholder.value = data.placeholder || ''
            waitingForInput.value = true
          },
        },
        controller.signal,
      )

      await reloadSidebarData()
    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        return
      }

      errorMessage.value = '请求失败，请检查后端服务或大模型配置。'
      finalizeAssistantStream('请求失败，请检查后端服务或设置页中的大模型配置。')
    } finally {
      chatStreaming.value = false
      taskStreaming.value = false
      chatStreamController = null
    }
  }

  async function sendMessageValue(value: string) {
    const trimmed = value.trim()
    if (!trimmed || loading.value || chatStreaming.value || taskStreaming.value) {
      return
    }

    errorMessage.value = ''
    messages.value.push(createLocalMessage('user', trimmed))
    messages.value.push(createLocalMessage('assistant', ''))
    loading.value = true

    try {
      const targetNodeId = selectedNodeId.value || availableNodes.value[0]?.id || ''
      const targetModelId = selectedModelId.value || availableModels.value.find((m) => m.is_default)?.id || ''
      await submitChatMessage(trimmed, targetNodeId, targetModelId)
    } catch {
      errorMessage.value = '请求失败，请检查后端服务或大模型配置。'
      finalizeAssistantStream('请求失败，请检查后端服务或设置页中的大模型配置。')
    } finally {
      loading.value = false
    }
  }

  async function submitMessage() {
    const value = input.value.trim()
    if (!value) {
      return
    }

    input.value = ''
    await sendMessageValue(value)
  }

  async function retryAssistantMessage(messageId: string) {
    const source = findRetrySourceMessage(messageId)
    if (!source) {
      ElMessage.warning('未找到可重答的上一条用户提问')
      return
    }

    await sendMessageValue(source.content)
  }

  async function confirmActiveTask(approved: boolean) {
    if (!activeTaskId.value || confirming.value) {
      return
    }

    confirming.value = true
    errorMessage.value = ''
    waitingForConfirm.value = false

    const riskReason = taskRiskReason.value

    try {
      const updatedTask = await confirmTask(activeTaskId.value, { approved })

      if (approved) {
        connectTaskStream(updatedTask.id)
      } else {
        closeTaskStream()
        appendAssistantMessage(`已拒绝\n原因：${riskReason}`)
        await reloadSidebarData()
      }
    } catch {
      errorMessage.value = '更新任务确认状态失败。'
    } finally {
      confirming.value = false
    }
  }

  async function stopActiveTask() {
    if (!activeTaskId.value || confirming.value) {
      return
    }

    closeTaskStream()
    errorMessage.value = ''
    try {
      await stopTask(activeTaskId.value)
      if (conversationId.value) {
        await loadChatMessages(conversationId.value)
      }
      await reloadSidebarData()
      ElMessage.success('任务已停止')
    } catch {
      errorMessage.value = '停止任务失败。'
    }
  }

  async function restartActiveTask() {
    if (!activeTaskId.value || confirming.value) {
      return
    }

    closeTaskStream()
    errorMessage.value = ''
    try {
      await restartTask(activeTaskId.value)
      if (conversationId.value) {
        await loadChatMessages(conversationId.value)
      }
      await reloadSidebarData()
      connectTaskStream(activeTaskId.value)
      ElMessage.success('任务已重新启动')
    } catch {
      errorMessage.value = '重启任务失败。'
    }
  }

  async function submitTaskInput(userInput: string) {
    if (!activeTaskId.value || !userInput.trim()) {
      return
    }

    const taskId = activeTaskId.value
    closeTaskStream()
    errorMessage.value = ''
    loading.value = true
    waitingForInput.value = false

    try {
      await provideTaskInput(taskId, { user_input: userInput.trim() })

      const lastMessage = messages.value[messages.value.length - 1]
      if (lastMessage?.role === 'assistant' && lastMessage.content.includes('需要您的输入')) {
        lastMessage.content = `用户输入: ${userInput.trim()}`
      }

      await reloadSidebarData()

      const continueUrl = buildTaskContinueUrl(taskId)
      taskStreaming.value = true
      const eventSource = new EventSource(continueUrl)

      eventSource.addEventListener('conversation.message', (event) => {
        const payload = JSON.parse((event as MessageEvent).data) as { conversation_id: string; type: string; content: string }
        const message = formatConversationMessage(payload.type, payload.content)
        if (message) {
          appendAssistantMessage(message)
        }
      })

      eventSource.addEventListener('conversation.input', (event) => {
        const payload = JSON.parse((event as MessageEvent).data) as { conversation_id: string; question: string; input_type: string; options?: string[]; placeholder?: string }
        inputQuestion.value = payload.question
        inputType.value = payload.input_type as 'text' | 'select' | 'multiselect'
        inputOptions.value = payload.options || []
        inputPlaceholder.value = payload.placeholder || ''
        waitingForInput.value = true
      })

      eventSource.addEventListener('conversation.done', () => {
        eventSource.close()
        taskStreaming.value = false
        void reloadSidebarData()
      })

      eventSource.onerror = () => {
        eventSource.close()
        taskStreaming.value = false
        void reloadSidebarData()
      }

      taskEventSource = eventSource
    } catch {
      errorMessage.value = '提交用户输入失败。'
      appendAssistantMessage('提交用户输入失败，请重试。')
    } finally {
      loading.value = false
    }
  }

  async function removeChatItem(targetChatId: string) {
    if (!targetChatId) {
      return
    }

    try {
      await ElMessageBox.confirm('删除后将同时移除该对话下的消息和关联任务，是否继续？', '删除对话', {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
      })
    } catch {
      return
    }

    errorMessage.value = ''
    try {
      await deleteChat(targetChatId)
      if (conversationId.value === targetChatId) {
        resetConversationState()
        input.value = ''
        void router.replace({ path: '/chat' })
      }
      await reloadSidebarData()
      ElMessage.success('对话已删除')
    } catch {
      errorMessage.value = '删除对话失败。'
    }
  }

  onBeforeUnmount(() => {
    closeStreams()
  })

  onMounted(() => {
    const routeConversationId = typeof route.query.conversation_id === 'string' ? route.query.conversation_id : ''
    const lastConversationId = localStorage.getItem(LAST_CONVERSATION_ID_KEY) ?? ''
    const initialConversationId = routeConversationId || lastConversationId

    if (initialConversationId) {
      void switchChat(initialConversationId)
    }
    void reloadSidebarData()
    void loadNodes()
    void loadModels()
    void loadViewerMeta()
  })

  watch(
    () => route.query.conversation_id,
    (value) => {
      const nextConversationId = typeof value === 'string' ? value : ''
      if (nextConversationId && nextConversationId !== conversationId.value) {
        void switchChat(nextConversationId)
      }
    },
  )

  const conversationLabel = computed(() => conversationId.value || 'new')
  const selectedModel = computed(() => availableModels.value.find((item) => item.id === selectedModelId.value) ?? null)
  const assistantTitle = computed(() => selectedModel.value?.name || '模型')
  const assistantLabel = computed(() => shortenLabel(assistantTitle.value, 8) || '模型')
  const userTitle = computed(() => currentUserName.value || '用户')
  const userLabel = computed(() => shortenLabel(userTitle.value, 8) || '用户')
  const selectedNode = computed(() => availableNodes.value.find((item) => item.id === selectedNodeId.value) ?? null)
  const streaming = computed(() => chatStreaming.value || taskStreaming.value)
  const streamingMessageId = computed(() => {
    if (!streaming.value) {
      return undefined
    }
    const lastMessage = messages.value[messages.value.length - 1]
    if (lastMessage?.role === 'assistant') {
      return lastMessage.id
    }
    return undefined
  })
  const activeChatTitle = computed(() => chats.value.find((item) => item.id === conversationId.value)?.title || '新对话')
  const filteredChats = computed(() => {
    if (!selectedNodeId.value) {
      return chats.value
    }
    return chats.value.filter((item) => !item.node_id || item.node_id === selectedNodeId.value)
  })
  const chatGroups = computed(() => buildChatGroups(filteredChats.value, sidebarSearch.value))
  const visibleChatCount = computed(() => chatGroups.value.reduce((total, group) => total + group.items.length, 0))
  const hasChatResults = computed(() => chatGroups.value.some((group) => group.items.length > 0))
  const hasMoreChats = computed(() => chats.value.length < chatTotal.value)
  const latestAssistantMessage = computed(() => {
    for (let index = messages.value.length - 1; index >= 0; index -= 1) {
      const item = messages.value[index]
      if (item.role === 'assistant' && item.content) {
        return item
      }
    }
    return null
  })
  const actionableAssistantMessageIds = computed(() => {
    const latestMessage = latestAssistantMessage.value
    if (!latestMessage) {
      return []
    }
    if (chatStreaming.value) {
      return []
    }
    return [latestMessage.id]
  })
  const retryableAssistantMessageIds = computed(() => {
    const actionableIds = new Set(actionableAssistantMessageIds.value)
    return messages.value.filter((item) => actionableIds.has(item.id) && !!findRetrySourceMessage(item.id)).map((item) => item.id)
  })
  const canStopTask = computed(() => !!activeTaskId.value && taskStreaming.value)
  const canRestartTask = computed(() => !!activeTaskId.value && !taskStreaming.value)
  const taskApprovalMessageId = computed(() => {
    if (!waitingForConfirm.value) {
      return ''
    }
    for (let index = messages.value.length - 1; index >= 0; index -= 1) {
      const item = messages.value[index]
      if (item.role !== 'assistant' && item.content?.includes('需要人工确认')) {
        return item.id
      }
    }
    const lastMessage = messages.value[messages.value.length - 1]
    return lastMessage?.role === 'assistant' ? lastMessage.id : ''
  })
  const taskInputRequest = computed(() => {
    if (!waitingForInput.value || !inputQuestion.value) {
      return undefined
    }
    return {
      question: inputQuestion.value,
      input_type: inputType.value || 'text',
      options: inputOptions.value,
      placeholder: inputPlaceholder.value,
    }
  })

  const taskUserInput = computed(() => {
    return undefined
  })

  return {
    activeTaskId,
    activeChatTitle,
    actionableAssistantMessageIds,
    availableNodes,
    availableModels,
    assistantLabel,
    assistantTitle,
    canRestartTask,
    canStopTask,
    chatStreaming,
    chats,
    chatGroups,
    chatTotal,
    confirming,
    copyMessage,
    errorMessage,
    hasChatResults,
    hasMoreChats,
    input,
    loadMoreChats,
    loading,
    messages,
    reloadSidebarData,
    removeChatItem,
    restartActiveTask,
    retryAssistantMessage,
    retryableAssistantMessageIds,
    selectedNode,
    selectedNodeId,
    selectedModel,
    selectedModelId,
    setSelectedNodeId,
    setSelectedModelId,
    sidebarSearch,
    sidebarLoading,
    startNewConversation,
    stopActiveTask,
    stopChatResponse,
    streaming,
    streamingMessageId,
    submitMessage,
    submitTaskInput,
    switchChat,
    taskApprovalMessageId,
    taskInputRequest,
    taskRiskReason,
    taskUserInput,
    confirmActiveTask,
    userLabel,
    userTitle,
    visibleChatCount,
    conversationLabel,
    conversationId,
    formatDateTime,
  }
}
