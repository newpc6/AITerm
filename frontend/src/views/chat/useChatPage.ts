import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { getAuthToken } from '@/auth'
import {
  buildConversationContinueUrl,
  confirmConversationExecute,
  deleteChat,
  getAuthStatus,
  getChat,
  getChatMessages,
  getChats,
  getModels,
  getNodes,
  provideConversationInput,
  restartConversationExecute,
  stopConversationExecute,
  streamChat,
} from '@/api/aiterm'
import { getApiBaseUrl } from '@/config'
import { formatDateTime } from '@/utils/datetime'
import type { ChatItem, ModelConfigItem, NodeItem } from '@/types/api'
import type { ChatMessage } from '@/types/chat'

const LAST_CHAT_ID_KEY = 'aiterm:last-chat-id'
type SidebarGroup<T> = {
  key: string
  label: string
  items: T[]
}

type ExecuteOutputKind = 'stdout' | 'stderr' | 'plan' | 'plan.info' | 'approval' | 'step.start' | 'step.result' | 'repair.analysis' | 'repair.retry' | 'repair.stop' | 'summary' | 'input.request'

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
    // JSON 解析失败，直接使用原始内容
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

function createInitialMessages(): ChatMessage[] {
  return [createLocalMessage('assistant', '你好！有什么可以帮助你的吗？')]
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
    if (!includesKeyword([item.title ?? undefined, item.summary, item.id], keyword)) {
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
  const executeStreaming = ref(false)
  const errorMessage = ref('')
  const sidebarLoading = ref(false)
  const sidebarSearch = ref('')
  const chatId = ref('')
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

  const executeStatus = ref('')
  const executeRiskReason = ref('')
  const inputQuestion = ref('')
  const inputType = ref<'text' | 'select' | 'multiselect'>('text')
  const inputOptions = ref<string[]>([])
  const inputPlaceholder = ref('')
  const waitingForInput = ref(false)
  const waitingForConfirm = ref(false)
  const reasoningBuffer = ref('')
  const reasoningStartTime = ref<number | null>(null)
  const isReasoningActive = ref(false)
  const reasoningDuration = ref<number | null>(null)
  const answerBuffer = ref('')
  const currentIteration = ref(0)
  const iterationsData = ref<
    Array<{
      input?: string
      full_input?: string
      thinking?: string
      thinking_duration?: number
      thinking_start_time?: string
      tool_calls?: Array<{ name: string; arguments: string; result: string; success: boolean; timestamp?: string }>
      content?: string
    }>
  >([])

  const lastUsage = ref<{
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
    prompt_cache_hit_tokens?: number
    prompt_cache_miss_tokens?: number
    reasoning_tokens?: number
  } | null>(null)

  const conversationTotalUsage = ref({
    prompt_tokens: 0,
    completion_tokens: 0,
    total_tokens: 0,
    reasoning_tokens: 0,
  })

  const displaySettings = ref({
    showThinking: true,
    expandThinking: false,
    showTools: true,
    expandTools: false,
    showInput: true,
    expandInput: false,
    showFullInput: false,
    expandFullInput: false,
    autoCollapse: true,
  })

  const showShareDialog = ref(false)

  let executeEventSource: EventSource | null = null
  let chatStreamController: AbortController | null = null

  function resetConversationState() {
    closeStreams()
    chatId.value = ''
    messages.value = createInitialMessages()
    lastUsage.value = null
    conversationTotalUsage.value = { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0, reasoning_tokens: 0 }
    localStorage.removeItem(LAST_CHAT_ID_KEY)
  }

  function startNewConversation() {
    resetConversationState()
    input.value = ''
    void router.replace({ path: '/chat' })
  }

  function appendAssistantMessage(content: string, type?: string) {
    if (!content || !content.trim()) {
      return
    }
    const lastMessage = messages.value[messages.value.length - 1]
    if (lastMessage?.role === 'assistant' && !lastMessage.content.trim()) {
      lastMessage.content = content
      if (type) {
        lastMessage.type = type as ChatMessage['type']
      }
    } else {
      const msg = createLocalMessage('assistant', content)
      if (type) {
        msg.type = type as ChatMessage['type']
      }
      messages.value.push(msg)
    }
  }

  function formatExecuteOutputMessage(stream: string, content: string) {
    const normalized = content.trim()
    if (!normalized) {
      return ''
    }

    switch (stream as ExecuteOutputKind) {
      case 'stdout':
        return normalized
      case 'stderr':
        return `[错误] ${normalized}`
      case 'plan.info':
        return normalized
      case 'plan':
        return `计划步骤如下：\n${normalized}`
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
        return `计划步骤如下：\n${normalized}`
      case 'step':
        return normalized
      case 'output':
        return normalized
      case 'approval':
        return normalized
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
      const [messagesData, chatData] = await Promise.all([getChatMessages(targetChatId), getChat(targetChatId)])
      messages.value = messagesData.items.map((item) => createMessageFromApi(item)).filter((msg) => msg.content && msg.content.trim())

      lastUsage.value = null
      conversationTotalUsage.value = { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0, reasoning_tokens: 0 }
      for (const msg of messages.value) {
        if (msg.role === 'assistant' && msg.metadata?.usage) {
          const u = msg.metadata.usage as Record<string, number>
          conversationTotalUsage.value.prompt_tokens += u.prompt_tokens || 0
          conversationTotalUsage.value.completion_tokens += u.completion_tokens || 0
          conversationTotalUsage.value.total_tokens += u.total_tokens || 0
          conversationTotalUsage.value.reasoning_tokens += u.reasoning_tokens || 0
        }
      }

      if (messages.value.length === 0) {
        messages.value = createInitialMessages()
      }

      if (chatData.status === 'waiting_confirm') {
        waitingForConfirm.value = true
        for (let index = messages.value.length - 1; index >= 0; index -= 1) {
          const item = messages.value[index]
          if (item.role === 'assistant' && item.type === 'approval') {
            executeRiskReason.value = item.content
            break
          }
        }
      } else if (chatData.status === 'waiting_input') {
        waitingForInput.value = true
        for (let index = messages.value.length - 1; index >= 0; index -= 1) {
          const item = messages.value[index]
          if (item.role === 'assistant' && item.type === 'input' && item.metadata) {
            const meta = item.metadata as import('@/types/chat').InputMetadata
            inputQuestion.value = meta.question || ''
            inputType.value = (meta.input_type as 'text' | 'select' | 'multiselect') || 'text'
            inputOptions.value = meta.options || []
            inputPlaceholder.value = meta.placeholder || ''
            break
          }
        }
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
    chatId.value = targetChatId
    localStorage.setItem(LAST_CHAT_ID_KEY, targetChatId)
    void router.replace({
      path: '/chat',
      query: {
        chat_id: targetChatId,
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

  function closeExecuteStream() {
    if (executeEventSource) {
      executeEventSource.close()
      executeEventSource = null
    }
    executeStreaming.value = false
  }

  function abortChatStream() {
    if (chatStreamController) {
      chatStreamController.abort()
      chatStreamController = null
    }
    chatStreaming.value = false
  }

  function closeStreams() {
    closeExecuteStream()
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

  function ensureAssistantPlaceholder() {
    const lastMessage = messages.value[messages.value.length - 1]
    if (lastMessage?.role === 'assistant') {
      return lastMessage
    }

    const placeholder = createLocalMessage('assistant', '')
    messages.value.push(placeholder)
    return placeholder
  }

  function appendAssistantDelta(delta: string, iteration?: number) {
    const placeholder = ensureAssistantPlaceholder()
    answerBuffer.value += delta
    placeholder.content = answerBuffer.value
    if (iterationsData.value.length > 0) {
      const iterIndex = (iteration || 1) - 1
      if (iterationsData.value[iterIndex]) {
        iterationsData.value[iterIndex].content = (iterationsData.value[iterIndex].content || '') + delta
      }
      placeholder.metadata = {
        ...placeholder.metadata,
        iterations: iterationsData.value,
      }
    } else if (reasoningBuffer.value) {
      placeholder.metadata = {
        ...placeholder.metadata,
        thinking: reasoningBuffer.value,
      }
    }
  }

  function appendReasoningDelta(delta: string, iteration?: number) {
    if (!reasoningStartTime.value) {
      reasoningStartTime.value = Date.now()
    }
    isReasoningActive.value = true
    reasoningBuffer.value += delta
    const placeholder = ensureAssistantPlaceholder()
    placeholder.content = answerBuffer.value
    if (iterationsData.value.length > 0) {
      const iterIndex = (iteration || 1) - 1
      if (iterationsData.value[iterIndex]) {
        iterationsData.value[iterIndex].thinking = reasoningBuffer.value
      }
      placeholder.metadata = {
        ...placeholder.metadata,
        iterations: iterationsData.value,
      }
    } else {
      placeholder.metadata = {
        ...placeholder.metadata,
        thinking: reasoningBuffer.value,
      }
    }
  }

  function handleIterationStart(iteration: number, input: string, fullInput?: string) {
    currentIteration.value = iteration
    reasoningBuffer.value = ''
    reasoningStartTime.value = null
    while (iterationsData.value.length < iteration) {
      iterationsData.value.push({})
    }
    iterationsData.value[iteration - 1] = {
      input,
      full_input: fullInput,
      thinking: '',
      tool_calls: [],
      content: '',
    }
    const placeholder = ensureAssistantPlaceholder()
    placeholder.metadata = {
      ...placeholder.metadata,
      iterations: iterationsData.value,
    }
  }

  function handleReasoningStart(iteration: number | undefined, timestamp: string) {
    const iterIndex = (iteration || currentIteration.value || 1) - 1
    while (iterationsData.value.length <= iterIndex) {
      iterationsData.value.push({})
    }
    if (!iterationsData.value[iterIndex]) {
      iterationsData.value[iterIndex] = {}
    }
    iterationsData.value[iterIndex].thinking_start_time = timestamp
    const placeholder = ensureAssistantPlaceholder()
    placeholder.metadata = {
      ...placeholder.metadata,
      iterations: iterationsData.value,
      current_thinking: '',
    }
  }

  function handleToolCall(iteration: number | undefined, name: string, args: string, result: string, timestamp?: string) {
    const iterIndex = (iteration || currentIteration.value || 1) - 1
    while (iterationsData.value.length <= iterIndex) {
      iterationsData.value.push({})
    }
    if (!iterationsData.value[iterIndex]) {
      iterationsData.value[iterIndex] = { tool_calls: [] }
    }
    if (!iterationsData.value[iterIndex].tool_calls) {
      iterationsData.value[iterIndex].tool_calls = []
    }
    iterationsData.value[iterIndex].tool_calls!.push({
      name,
      arguments: args,
      result,
      success: result.includes('success') && result.toLowerCase().includes('true'),
      timestamp,
    })
    const placeholder = ensureAssistantPlaceholder()
    placeholder.metadata = {
      ...placeholder.metadata,
      iterations: iterationsData.value,
    }
  }

  function finalizeAssistantStream(reply: string, iterations?: unknown[], totalDuration?: number) {
    const placeholder = ensureAssistantPlaceholder()
    placeholder.content = reply

    let preservedFullInput: string | undefined = undefined
    for (const iter of iterationsData.value) {
      if (iter.full_input) {
        preservedFullInput = iter.full_input
        break
      }
    }

    if (iterations && Array.isArray(iterations) && iterations.length > 0) {
      placeholder.metadata = {
        ...placeholder.metadata,
        iterations,
        total_duration: totalDuration || 0,
        full_input: preservedFullInput || (placeholder.metadata?.full_input as string),
      }
    } else if (iterationsData.value.length > 0) {
      placeholder.metadata = {
        ...placeholder.metadata,
        iterations: iterationsData.value,
        total_duration: totalDuration || 0,
        full_input: preservedFullInput || (placeholder.metadata?.full_input as string),
      }
    } else if (reasoningBuffer.value) {
      placeholder.metadata = {
        ...placeholder.metadata,
        thinking: reasoningBuffer.value,
        reasoning_duration: reasoningDuration.value || 0,
        total_duration: totalDuration || 0,
      }
    } else {
      placeholder.metadata = {
        ...placeholder.metadata,
        total_duration: totalDuration || 0,
      }
    }
    reasoningBuffer.value = ''
    reasoningStartTime.value = null
    reasoningDuration.value = null
    answerBuffer.value = ''
    isReasoningActive.value = false
    currentIteration.value = 0
    iterationsData.value = []
  }

  async function submitChatMessage(value: string, targetNodeId: string, targetModelId: string) {
    abortChatStream()
    chatStreaming.value = true
    executeStreaming.value = false
    const controller = new AbortController()
    chatStreamController = controller

    try {
      await streamChat(
        {
          chat_id: chatId.value || undefined,
          node_id: targetNodeId,
          model_id: targetModelId || undefined,
          message: value,
        },
        {
          onMeta: (data) => {
            chatId.value = data.chat_id
            if ((data as { mode?: string }).mode === 'execute') {
              executeStreaming.value = true
            }
            localStorage.setItem(LAST_CHAT_ID_KEY, data.chat_id)
            void router.replace({
              path: '/chat',
              query: {
                chat_id: data.chat_id,
              },
            })
          },
          onDelta: (data) => {
            if (!chatId.value) {
              chatId.value = data.chat_id
            }
            appendAssistantDelta(data.delta, (data as { iteration?: number }).iteration)
          },
          onReasoning: (data) => {
            if (!chatId.value) {
              chatId.value = data.chat_id
            }
            appendReasoningDelta(data.delta, data.iteration)
          },
          onReasoningStart: (data) => {
            isReasoningActive.value = true
            handleReasoningStart(data.iteration, data.timestamp)
          },
          onReasoningDone: (data) => {
            isReasoningActive.value = false
            reasoningDuration.value = data.duration
            if (iterationsData.value.length > 0 && data.iteration) {
              const iterIndex = data.iteration - 1
              if (iterationsData.value[iterIndex]) {
                iterationsData.value[iterIndex].thinking_duration = data.duration
              }
            }
          },
          onIterationStart: (data) => {
            handleIterationStart(data.iteration, data.input, (data as { full_input?: string }).full_input)
          },
          onToolCall: (data) => {
            handleToolCall(data.iteration, data.name, data.arguments, data.result, (data as { timestamp?: string }).timestamp)
          },
          onDone: (data) => {
            chatId.value = data.chat_id
            finalizeAssistantStream(data.reply, (data as { iterations?: unknown[] }).iterations, data.total_duration)
            const usageData = (data as Record<string, unknown>).usage as Record<string, number> | undefined
            if (usageData) {
              lastUsage.value = {
                prompt_tokens: usageData.prompt_tokens || 0,
                completion_tokens: usageData.completion_tokens || 0,
                total_tokens: usageData.total_tokens || 0,
                prompt_cache_hit_tokens: usageData.prompt_cache_hit_tokens as number | undefined,
                prompt_cache_miss_tokens: usageData.prompt_cache_miss_tokens as number | undefined,
                reasoning_tokens: usageData.reasoning_tokens as number | undefined,
              }
              conversationTotalUsage.value = {
                prompt_tokens: conversationTotalUsage.value.prompt_tokens + (usageData.prompt_tokens || 0),
                completion_tokens: conversationTotalUsage.value.completion_tokens + (usageData.completion_tokens || 0),
                total_tokens: conversationTotalUsage.value.total_tokens + (usageData.total_tokens || 0),
                reasoning_tokens: conversationTotalUsage.value.reasoning_tokens + (usageData.reasoning_tokens || 0),
              }
            }
          },
          onError: (data) => {
            errorMessage.value = data.error
            finalizeAssistantStream(`请求失败：${data.error}`)
          },
          onConversationMessage: (data) => {
            if (data.type === 'approval') {
              waitingForConfirm.value = true
              executeRiskReason.value = data.content
            }
            const message = formatConversationMessage(data.type, data.content)
            if (message) {
              appendAssistantMessage(message, data.type)
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
      executeStreaming.value = false
      chatStreamController = null
    }
  }

  async function sendMessageValue(value: string) {
    const trimmed = value.trim()
    if (!trimmed || loading.value || chatStreaming.value || executeStreaming.value) {
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

  async function confirmActiveExecute(approved: boolean) {
    if (!chatId.value || confirming.value) {
      return
    }

    confirming.value = true
    errorMessage.value = ''
    waitingForConfirm.value = false

    const riskReason = executeRiskReason.value
    const currentChatId = chatId.value

    try {
      await confirmConversationExecute(currentChatId, { approved })

      if (approved) {
        const continueUrl = buildConversationContinueUrl(currentChatId)
        executeStreaming.value = true
        const eventSource = new EventSource(continueUrl)

        eventSource.addEventListener('conversation.message', (event) => {
          const payload = JSON.parse((event as MessageEvent).data) as { conversation_id: string; type: string; content: string }
          if (payload.type === 'approval') {
            waitingForConfirm.value = true
            executeRiskReason.value = payload.content
          }
          const message = formatConversationMessage(payload.type, payload.content)
          if (message) {
            appendAssistantMessage(message, payload.type)
          }
        })

        eventSource.addEventListener('conversation.error', (event) => {
          const payload = JSON.parse((event as MessageEvent).data) as { error: string }
          appendAssistantMessage(`[错误] ${payload.error}`)
          eventSource.close()
          executeStreaming.value = false
          void reloadSidebarData()
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
          executeStreaming.value = false
          void reloadSidebarData()
        })

        eventSource.onerror = () => {
          eventSource.close()
          executeStreaming.value = false
          void reloadSidebarData()
        }

        executeEventSource = eventSource
      } else {
        closeExecuteStream()
        appendAssistantMessage(`已拒绝\n原因：${riskReason}`)
        await reloadSidebarData()
      }
    } catch {
      errorMessage.value = '更新任务确认状态失败。'
    } finally {
      confirming.value = false
    }
  }

  async function stopActiveExecute() {
    if (!chatId.value || confirming.value) {
      return
    }

    closeExecuteStream()
    errorMessage.value = ''
    try {
      await stopConversationExecute(chatId.value)
      await loadChatMessages(chatId.value)
      await reloadSidebarData()
      ElMessage.success('执行已停止')
    } catch {
      errorMessage.value = '停止执行失败。'
    }
  }

  async function restartActiveExecute() {
    if (!chatId.value || confirming.value) {
      return
    }

    closeExecuteStream()
    errorMessage.value = ''
    try {
      await restartConversationExecute(chatId.value)
      await loadChatMessages(chatId.value)
      await reloadSidebarData()
      ElMessage.success('执行已重新启动')
    } catch {
      errorMessage.value = '重启执行失败。'
    }
  }

  async function submitExecuteInput(userInput: string) {
    if (!chatId.value || !userInput.trim()) {
      return
    }

    const currentChatId = chatId.value
    closeExecuteStream()
    errorMessage.value = ''
    loading.value = true
    waitingForInput.value = false

    try {
      await provideConversationInput(currentChatId, { user_input: userInput.trim() })

      const lastMessage = messages.value[messages.value.length - 1]
      if (lastMessage?.role === 'assistant' && lastMessage.content.includes('需要您的输入')) {
        lastMessage.content = `用户输入: ${userInput.trim()}`
      }

      await reloadSidebarData()

      const continueUrl = buildConversationContinueUrl(currentChatId)
      executeStreaming.value = true
      const eventSource = new EventSource(continueUrl)

      eventSource.addEventListener('conversation.message', (event) => {
        const payload = JSON.parse((event as MessageEvent).data) as { conversation_id: string; type: string; content: string }
        const message = formatConversationMessage(payload.type, payload.content)
        if (message) {
          appendAssistantMessage(message, payload.type)
        }
      })

      eventSource.addEventListener('conversation.error', (event) => {
        const payload = JSON.parse((event as MessageEvent).data) as { error: string }
        appendAssistantMessage(`[错误] ${payload.error}`)
        eventSource.close()
        executeStreaming.value = false
        void reloadSidebarData()
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
        executeStreaming.value = false
        void reloadSidebarData()
      })

      eventSource.onerror = () => {
        eventSource.close()
        executeStreaming.value = false
        void reloadSidebarData()
      }

      executeEventSource = eventSource
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
      if (chatId.value === targetChatId) {
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
    const routeChatId = typeof route.query.chat_id === 'string' ? route.query.chat_id : ''
    const lastChatId = localStorage.getItem(LAST_CHAT_ID_KEY) ?? ''
    const initialChatId = routeChatId || lastChatId

    if (initialChatId) {
      void switchChat(initialChatId)
    }
    void reloadSidebarData()
    void loadNodes()
    void loadModels()
    void loadViewerMeta()
  })

  watch(
    () => route.query.chat_id,
    (value) => {
      const nextChatId = typeof value === 'string' ? value : ''
      if (nextChatId && nextChatId !== chatId.value) {
        void switchChat(nextChatId)
      }
    },
  )

  const conversationLabel = computed(() => chatId.value || 'new')
  const selectedModel = computed(() => availableModels.value.find((item) => item.id === selectedModelId.value) ?? null)
  const modelContextLength = computed(() => selectedModel.value?.context_length ?? null)
  const modelContextLimit = computed(() => {
    if (modelContextLength.value) return modelContextLength.value
    const rounds = displaySettings.value as unknown as { chat_history_limit?: number }
    return null
  })
  const usagePercentage = computed(() => {
    if (!lastUsage.value || !modelContextLength.value) return null
    const ratio = lastUsage.value.total_tokens / modelContextLength.value
    return Math.min(100, Math.round(ratio * 1000) / 10)
  })
  const usageColor = computed(() => {
    if (!usagePercentage.value) return '#67c23a'
    if (usagePercentage.value > 80) return '#f56c6c'
    if (usagePercentage.value > 50) return '#e6a23c'
    return '#67c23a'
  })
  const hasUsage = computed(() => lastUsage.value !== null || conversationTotalUsage.value.total_tokens > 0)
  const assistantTitle = computed(() => selectedModel.value?.name || '模型')
  const assistantLabel = computed(() => shortenLabel(assistantTitle.value, 8) || '模型')
  const userTitle = computed(() => currentUserName.value || '用户')
  const userLabel = computed(() => shortenLabel(userTitle.value, 8) || '用户')
  const selectedNode = computed(() => availableNodes.value.find((item) => item.id === selectedNodeId.value) ?? null)
  const streaming = computed(() => chatStreaming.value || executeStreaming.value)
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
  const activeChatTitle = computed(() => chats.value.find((item) => item.id === chatId.value)?.title || '新对话')
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
  const canStopExecute = computed(() => !!chatId.value && executeStreaming.value)
  const canRestartExecute = computed(() => !!chatId.value && !executeStreaming.value)
  const executeApprovalMessageId = computed(() => {
    if (!waitingForConfirm.value) {
      return ''
    }
    for (let index = messages.value.length - 1; index >= 0; index -= 1) {
      const item = messages.value[index]
      if (item.role === 'assistant' && item.type === 'approval') {
        return item.id
      }
    }
    for (let index = messages.value.length - 1; index >= 0; index -= 1) {
      const item = messages.value[index]
      if (item.role === 'assistant' && item.content?.includes('需要人工确认')) {
        return item.id
      }
    }
    const lastMessage = messages.value[messages.value.length - 1]
    return lastMessage?.role === 'assistant' ? lastMessage.id : ''
  })
  const executeInputRequest = computed(() => {
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

  const executeUserInput = computed(() => {
    return undefined
  })

  return {
    activeChatTitle,
    actionableAssistantMessageIds,
    availableNodes,
    availableModels,
    assistantLabel,
    assistantTitle,
    canRestartExecute,
    canStopExecute,
    chatStreaming,
    chats,
    chatGroups,
    chatTotal,
    confirming,
    copyMessage,
    errorMessage,
    hasChatResults,
    hasMoreChats,
    hasUsage,
    input,
    isReasoningActive,
    lastUsage,
    loadMoreChats,
    loading,
    messages,
    conversationTotalUsage,
    modelContextLength,
    modelContextLimit,
    usagePercentage,
    usageColor,
    reloadSidebarData,
    removeChatItem,
    restartActiveExecute,
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
    stopActiveExecute,
    stopChatResponse,
    streaming,
    streamingMessageId,
    submitMessage,
    submitExecuteInput,
    switchChat,
    executeApprovalMessageId,
    executeInputRequest,
    executeRiskReason,
    executeUserInput,
    confirmActiveExecute,
    userLabel,
    userTitle,
    visibleChatCount,
    conversationLabel,
    chatId,
    formatDateTime,
    displaySettings,
    showShareDialog,
  }
}
