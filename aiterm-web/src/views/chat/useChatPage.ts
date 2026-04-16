import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { getAuthToken } from '@/auth'
import {
  confirmTask,
  deleteConversation,
  deleteTask,
  getAuthStatus,
  getConversationMessages,
  getConversations,
  getLLMPublicInfo,
  getNodes,
  getTaskDetail,
  getTasks,
  restartTask,
  stopTask,
  streamConversation,
  submitConversation,
} from '@/api/aiterm'
import { getApiBaseUrl } from '@/config'
import { formatDateTime } from '@/utils/datetime'
import type { ConversationListItem, ConversationMode, NodeItem, TaskDetail, TaskItem, TaskStreamOutputData, TaskStreamStatusData } from '@/types/api'
import type { ChatMessage } from '@/types/chat'

const LAST_CONVERSATION_ID_KEY = 'aiterm:last-conversation-id'
type SidebarTab = 'conversations' | 'tasks'
type TaskStatusFilter = 'executing' | 'completed' | 'failed'
type SidebarGroup<T> = {
  key: string
  label: string
  items: T[]
}

type TaskOutputKind =
  | 'plan'
  | 'plan.info'
  | 'approval'
  | 'step.start'
  | 'step.result'
  | 'repair.analysis'
  | 'repair.retry'
  | 'repair.stop'
  | 'summary'

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

function createMessageFromApi(item: { id: string; role: ChatMessage['role']; content: string; created_at: string }): ChatMessage {
  return {
    id: item.id,
    role: item.role,
    content: item.content,
    createdAt: item.created_at,
  }
}

function buildEventSourceUrl(taskId: string) {
  const baseUrl = getApiBaseUrl().trim()
  const eventPath = `/api/tasks/${taskId}/events`
  const url = baseUrl ? new URL(eventPath, baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`) : new URL(eventPath, window.location.origin)
  const token = getAuthToken()
  if (token) {
    url.searchParams.set('access_token', token)
  }
  return url.toString()
}

function createInitialMessages(mode: ConversationMode): ChatMessage[] {
  return [
    createLocalMessage(
      'assistant',
      mode === 'task' ? '已进入任务模式，请描述希望执行的任务。任务执行过程和输出会持续写入会话记录。' : '已进入对话模式，你可以直接向模型提问，我会按一问一答的方式继续这个会话。',
    ),
  ]
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

function buildConversationGroups(items: ConversationListItem[], search: string): SidebarGroup<ConversationListItem>[] {
  const keyword = search.trim().toLowerCase()
  const now = Date.now()
  const dayMs = 24 * 60 * 60 * 1000
  const groups = new Map<string, SidebarGroup<ConversationListItem>>()

  for (const item of items) {
    if (!includesKeyword([item.title, item.last_message, item.id], keyword)) {
      continue
    }

    const age = now - parseTimestamp(item.updated_at)
    const key = age <= dayMs ? 'today' : age <= dayMs * 7 ? 'recent' : 'earlier'
    const label = key === 'today' ? '今天' : key === 'recent' ? '近 7 天' : '更早'
    if (!groups.has(key)) {
      groups.set(key, { key, label, items: [] })
    }
    groups.get(key)?.items.push(item)
  }

  return Array.from(groups.values())
}

function filterTasksByStatus(items: TaskItem[], search: string, filter: TaskStatusFilter): TaskItem[] {
  const keyword = search.trim().toLowerCase()
  return items.filter((item) => {
    const matchesFilter =
      filter === 'executing'
        ? ['waiting_confirm', 'pending', 'analyzing', 'executing'].includes(item.status)
        : filter === 'completed'
          ? item.status === 'completed'
          : ['failed', 'cancelled'].includes(item.status)

    return matchesFilter && includesKeyword([item.title, item.status, item.pending_command, item.risk_reason, item.id], keyword)
  })
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
  const activeMode = ref<ConversationMode>('chat')
  const sidebarTab = ref<SidebarTab>('conversations')
  const taskStatusFilter = ref<TaskStatusFilter>('executing')
  const selectedNodeId = ref('')
  const availableNodes = ref<NodeItem[]>([])
  const currentUserName = ref('用户')
  const currentModelName = ref('模型')
  const conversations = ref<ConversationListItem[]>([])
  const tasks = ref<TaskItem[]>([])
  const taskDetail = ref<TaskDetail | null>(null)
  const messages = ref<ChatMessage[]>(createInitialMessages('chat'))

  let taskEventSource: EventSource | null = null
  let chatStreamController: AbortController | null = null

  function resetConversationState() {
    closeStreams()
    conversationId.value = ''
    activeTaskId.value = ''
    activeMode.value = 'chat'
    taskDetail.value = null
    messages.value = createInitialMessages('chat')
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
      case 'plan.info':
        return normalized
      case 'plan':
        return `任务计划如下：\n${normalized}`
      case 'approval':
        return normalized
      case 'step.start':
      case 'step.result':
      case 'repair.analysis':
      case 'repair.retry':
      case 'repair.stop':
      case 'summary':
        return normalized
      default:
        return ''
    }
  }

  async function loadConversationMessages(targetConversationId: string) {
    try {
      const data = await getConversationMessages(targetConversationId)
      messages.value = data.items.map((item) => createMessageFromApi(item))

      if (messages.value.length === 0) {
        messages.value = createInitialMessages(activeMode.value)
      }

      if (data.latest_task_id) {
        activeTaskId.value = data.latest_task_id
        activeMode.value = 'task'
        await loadTaskDetail(data.latest_task_id)
        if (taskDetail.value?.node_id) {
          selectedNodeId.value = taskDetail.value.node_id
        }
      } else {
        activeTaskId.value = ''
        activeMode.value = 'chat'
        taskDetail.value = null
      }
    } catch {
      resetConversationState()
      void router.replace({ path: '/chat' })
      errorMessage.value = '该会话不存在或已被删除。'
    }
  }

  async function switchConversation(targetConversationId: string) {
    if (!targetConversationId) {
      return
    }

    closeStreams()
    conversationId.value = targetConversationId
    localStorage.setItem(LAST_CONVERSATION_ID_KEY, targetConversationId)
    await loadConversationMessages(targetConversationId)
  }

  async function openTaskFromSidebar(task: TaskItem) {
    sidebarTab.value = 'tasks'
    activeTaskId.value = task.id
    selectedNodeId.value = task.node_id
    await loadTaskDetail(task.id)
    await switchConversation(task.conversation_id)
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

  async function loadViewerMeta() {
    try {
      const [status, llmInfo] = await Promise.all([getAuthStatus(), getLLMPublicInfo()])
      currentUserName.value = status.user?.display_name || status.user?.username || '用户'
      currentModelName.value = llmInfo.model || '模型'
    } catch {
      currentUserName.value = '用户'
      currentModelName.value = '模型'
    }
  }

  async function loadConversations() {
    try {
      const data = await getConversations()
      conversations.value = data.items
    } catch {
      errorMessage.value = '历史会话接口不可用。'
    }
  }

  async function loadTasks() {
    try {
      const data = await getTasks()
      tasks.value = data.items
    } catch {
      errorMessage.value = '任务接口不可用。'
    }
  }

  async function reloadSidebarData() {
    sidebarLoading.value = true
    try {
      await Promise.all([loadConversations(), loadTasks()])
    } finally {
      sidebarLoading.value = false
    }
  }

  function setSelectedNodeId(value: string) {
    selectedNodeId.value = value
  }

  function setSidebarTab(value: SidebarTab) {
    sidebarTab.value = value
  }

  function setTaskStatusFilter(value: TaskStatusFilter) {
    taskStatusFilter.value = value
  }

  function setActiveMode(value: ConversationMode) {
    activeMode.value = value
    if (!conversationId.value && messages.value.length <= 1) {
      messages.value = createInitialMessages(value)
    }
    sidebarTab.value = value === 'task' ? 'tasks' : 'conversations'
  }

  async function loadTaskDetail(taskId: string) {
    try {
      taskDetail.value = await getTaskDetail(taskId)
      selectedNodeId.value = taskDetail.value.node_id
      updateTaskSnapshot(taskDetail.value)
    } catch {
      errorMessage.value = '任务详情接口不可用。'
    }
  }

  function updateTaskSnapshot(task: TaskItem | TaskDetail) {
    const nextItem: TaskItem = {
      id: task.id,
      title: task.title,
      status: task.status,
      progress: task.progress,
      conversation_id: task.conversation_id,
      node_id: task.node_id,
      pending_command: task.pending_command,
      risk_reason: task.risk_reason,
      created_at: task.created_at,
    }

    const index = tasks.value.findIndex((item) => item.id === nextItem.id)
    if (index >= 0) {
      tasks.value[index] = nextItem
      return
    }
    tasks.value = [nextItem, ...tasks.value]
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

    taskEventSource.addEventListener('task.status', (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as TaskStreamStatusData
      if (taskDetail.value && taskDetail.value.id === payload.task_id) {
        taskDetail.value = {
          ...taskDetail.value,
          status: payload.status,
          progress: payload.progress,
        }
        updateTaskSnapshot(taskDetail.value)
      }
    })

    taskEventSource.addEventListener('task.output', (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as TaskStreamOutputData
      const message = formatTaskOutputMessage(payload.stream, payload.content)
      if (message) {
        appendAssistantMessage(message)
      }
    })

    taskEventSource.onerror = async () => {
      closeTaskStream()
      await loadTaskDetail(taskId)
      await reloadSidebarData()
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

  async function submitChatMessage(value: string, targetNodeId: string) {
    abortChatStream()
    chatStreaming.value = true
    const controller = new AbortController()
    chatStreamController = controller

    try {
      await streamConversation(
        {
          conversation_id: conversationId.value,
          node_id: targetNodeId,
          message: value,
          mode: 'chat',
        },
        {
          onMeta: (data) => {
            conversationId.value = data.conversation_id
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
        },
        controller.signal,
      )

      activeTaskId.value = ''
      taskDetail.value = null
      await reloadSidebarData()
    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        return
      }

      errorMessage.value = '对话流请求失败，请检查后端服务或大模型配置。'
      finalizeAssistantStream('对话流请求失败，请检查后端服务或设置页中的大模型配置。')
    } finally {
      chatStreaming.value = false
      chatStreamController = null
    }
  }

  async function submitTaskMessage(value: string, targetNodeId: string) {
    const data = await submitConversation({
      conversation_id: conversationId.value,
      node_id: targetNodeId,
      message: value,
      mode: 'task',
    })

    conversationId.value = data.conversation_id
    localStorage.setItem(LAST_CONVERSATION_ID_KEY, data.conversation_id)
    void router.replace({
      path: '/chat',
      query: {
        conversation_id: data.conversation_id,
      },
    })
    await loadConversationMessages(data.conversation_id)
    await reloadSidebarData()
    if (data.task_id) {
      activeMode.value = 'task'
      sidebarTab.value = 'tasks'
      activeTaskId.value = data.task_id
      appendAssistantMessage(`当前任务编号：${data.task_id}`)
      await loadTaskDetail(data.task_id)
      if (taskDetail.value?.status === 'waiting_confirm') {
        appendAssistantMessage('任务正在等待确认后执行。')
      } else {
        connectTaskStream(data.task_id)
      }
    }
  }

  async function sendMessageValue(value: string) {
    const trimmed = value.trim()
    if (!trimmed || loading.value || chatStreaming.value || taskStreaming.value) {
      return
    }

    errorMessage.value = ''
    messages.value.push(createLocalMessage('user', trimmed))
    loading.value = true

    try {
      const targetNodeId = selectedNodeId.value || availableNodes.value[0]?.id || ''
      if (activeMode.value === 'chat') {
        await submitChatMessage(trimmed, targetNodeId)
      } else {
        await submitTaskMessage(trimmed, targetNodeId)
      }
    } catch {
      errorMessage.value = '请求失败，请检查后端服务或大模型配置。'
      appendAssistantMessage('请求失败，请检查后端服务或设置页中的大模型配置。')
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
    if (activeMode.value !== 'chat') {
      return
    }

    const source = findRetrySourceMessage(messageId)
    if (!source) {
      ElMessage.warning('未找到可重答的上一条用户提问')
      return
    }

    await sendMessageValue(source.content)
  }

  async function confirmActiveTask(approved: boolean) {
    if (!taskDetail.value || confirming.value) {
      return
    }

    confirming.value = true
    errorMessage.value = ''

    try {
      const updatedTask = await confirmTask(taskDetail.value.id, { approved })
      taskDetail.value = updatedTask
      updateTaskSnapshot(updatedTask)

      if (approved) {
        appendAssistantMessage(`任务 ${updatedTask.id} 命令已批准。`)
        connectTaskStream(updatedTask.id)
      } else {
        closeTaskStream()
        appendAssistantMessage(`任务 ${updatedTask.id} 命令已拒绝。`)
        await reloadSidebarData()
      }
    } catch {
      errorMessage.value = '更新任务确认状态失败。'
    } finally {
      confirming.value = false
    }
  }

  async function stopActiveTask() {
    if (!taskDetail.value || confirming.value) {
      return
    }

    closeTaskStream()
    errorMessage.value = ''
    try {
      const updatedTask = await stopTask(taskDetail.value.id)
      taskDetail.value = updatedTask
      updateTaskSnapshot(updatedTask)
      if (conversationId.value) {
        await loadConversationMessages(conversationId.value)
      }
      await reloadSidebarData()
      ElMessage.success('任务已停止')
    } catch {
      errorMessage.value = '停止任务失败。'
    }
  }

  async function restartActiveTask() {
    if (!taskDetail.value || confirming.value) {
      return
    }

    closeTaskStream()
    errorMessage.value = ''
    try {
      const updatedTask = await restartTask(taskDetail.value.id)
      taskDetail.value = updatedTask
      updateTaskSnapshot(updatedTask)
      if (conversationId.value) {
        await loadConversationMessages(conversationId.value)
      }
      await reloadSidebarData()
      connectTaskStream(updatedTask.id)
      ElMessage.success('任务已重新启动')
    } catch {
      errorMessage.value = '重启任务失败。'
    }
  }

  async function removeConversationItem(targetConversationId: string) {
    if (!targetConversationId) {
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
      await deleteConversation(targetConversationId)
      if (conversationId.value === targetConversationId) {
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

  async function removeTaskItem(taskId: string) {
    if (!taskId) {
      return
    }

    try {
      await ElMessageBox.confirm('删除后将移除当前任务记录，但会保留原对话消息，是否继续？', '删除任务', {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
      })
    } catch {
      return
    }

    if (activeTaskId.value === taskId) {
      closeTaskStream()
    }

    errorMessage.value = ''
    try {
      await deleteTask(taskId)
      if (activeTaskId.value === taskId) {
        activeTaskId.value = ''
        taskDetail.value = null
        if (conversationId.value) {
          await loadConversationMessages(conversationId.value)
        }
      }
      await reloadSidebarData()
      ElMessage.success('任务已删除')
    } catch {
      errorMessage.value = '删除任务失败。'
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
      void switchConversation(initialConversationId)
    }
    void reloadSidebarData()
    void loadNodes()
    void loadViewerMeta()
  })

  watch(
    () => route.query.conversation_id,
    (value) => {
      const nextConversationId = typeof value === 'string' ? value : ''
      if (nextConversationId && nextConversationId !== conversationId.value) {
        void switchConversation(nextConversationId)
      }
    },
  )

  const conversationLabel = computed(() => conversationId.value || 'new')
  const assistantTitle = computed(() => (activeMode.value === 'task' ? 'AITerm' : currentModelName.value || '模型'))
  const assistantLabel = computed(() => shortenLabel(assistantTitle.value, activeMode.value === 'task' ? 10 : 8) || '模型')
  const userTitle = computed(() => currentUserName.value || '用户')
  const userLabel = computed(() => shortenLabel(userTitle.value, 8) || '用户')
  const selectedNode = computed(() => availableNodes.value.find((item) => item.id === selectedNodeId.value) ?? null)
  const streaming = computed(() => chatStreaming.value || taskStreaming.value)
  const activeConversationTitle = computed(() => conversations.value.find((item) => item.id === conversationId.value)?.title || '新对话')
  const filteredConversations = computed(() => {
    const chatOnlyItems = conversations.value.filter((item) => !item.latest_task_id)
    if (!selectedNodeId.value) {
      return chatOnlyItems
    }
    return chatOnlyItems.filter((item) => !item.latest_node_id || item.latest_node_id === selectedNodeId.value)
  })
  const filteredTasks = computed(() => {
    if (!selectedNodeId.value) {
      return tasks.value
    }
    return tasks.value.filter((item) => item.node_id === selectedNodeId.value)
  })
  const conversationGroups = computed(() => buildConversationGroups(filteredConversations.value, sidebarSearch.value))
  const filteredTaskItems = computed(() => filterTasksByStatus(filteredTasks.value, sidebarSearch.value, taskStatusFilter.value))
  const visibleConversationCount = computed(() => conversationGroups.value.reduce((total, group) => total + group.items.length, 0))
  const visibleTaskCount = computed(() => filteredTaskItems.value.length)
  const hasConversationResults = computed(() => conversationGroups.value.some((group) => group.items.length > 0))
  const hasTaskResults = computed(() => filteredTaskItems.value.length > 0)
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
    if (activeMode.value !== 'chat') {
      return []
    }
    const actionableIds = new Set(actionableAssistantMessageIds.value)
    return messages.value.filter((item) => actionableIds.has(item.id) && !!findRetrySourceMessage(item.id)).map((item) => item.id)
  })
  const canStopTask = computed(() => !!taskDetail.value && ['waiting_confirm', 'pending', 'analyzing', 'executing'].includes(taskDetail.value.status))
  const canRestartTask = computed(() => !!taskDetail.value && ['waiting_confirm', 'completed', 'failed', 'cancelled'].includes(taskDetail.value.status))
  const taskApprovalMessageId = computed(() => {
    if (activeMode.value !== 'task' || taskDetail.value?.status !== 'waiting_confirm') {
      return ''
    }
    const pendingCommand = taskDetail.value.pending_command?.trim()
    for (let index = messages.value.length - 1; index >= 0; index -= 1) {
      const item = messages.value[index]
      if (item.role !== 'assistant' || !item.content) {
        continue
      }
      if (pendingCommand && item.content.includes(pendingCommand)) {
        return item.id
      }
      if (item.content.includes('等待人工确认后执行')) {
        return item.id
      }
    }
    return ''
  })

  return {
    activeTaskId,
    activeConversationTitle,
    activeMode,
    actionableAssistantMessageIds,
    availableNodes,
    assistantLabel,
    assistantTitle,
    canRestartTask,
    canStopTask,
    chatStreaming,
    confirming,
    copyMessage,
    conversations,
    conversationGroups,
    conversationLabel,
    errorMessage,
    filteredTaskItems,
    hasConversationResults,
    hasTaskResults,
    input,
    loading,
    messages,
    openTaskFromSidebar,
    reloadSidebarData,
    removeConversationItem,
    removeTaskItem,
    restartActiveTask,
    retryAssistantMessage,
    retryableAssistantMessageIds,
    selectedNode,
    selectedNodeId,
    setActiveMode,
    setSelectedNodeId,
    setSidebarTab,
    sidebarSearch,
    sidebarLoading,
    sidebarTab,
    startNewConversation,
    setTaskStatusFilter,
    stopActiveTask,
    stopChatResponse,
    streaming,
    submitMessage,
    taskApprovalMessageId,
    taskDetail,
    taskStatusFilter,
    switchConversation,
    confirmActiveTask,
    tasks,
    userLabel,
    userTitle,
    visibleConversationCount,
    visibleTaskCount,
    formatDateTime,
  }
}
