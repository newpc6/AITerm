import { http } from './http'
import { getAuthToken } from '@/auth'
import { getApiBaseUrl } from '@/config'
import type {
  ApiResponse,
  AuthChangePasswordPayload,
  AuthLoginData,
  AuthLoginPayload,
  AuthSettingsData,
  AuthSettingsPayload,
  AuthStatusData,
  ConversationData,
  ConversationStreamDeltaData,
  ConversationStreamDoneData,
  ConversationStreamMetaData,
  ConversationListData,
  ConversationMessagesData,
  ConversationPayload,
  HealthData,
  ModelConfigItem,
  ModelConfigListData,
  ModelConfigPayload,
  GlobalSettingsData,
  GlobalSettingsPayload,
  NodeItem,
  NodeListData,
  NodePayload,
  ExecuteConfirmPayload,
  ExecuteDetail,
  ExecuteInputPayload,
  ExecuteListData,
  TerminalExecuteData,
  TerminalExecutePayload,
  UserItem,
  UserListData,
  UserPayload,
  UserResetPasswordPayload,
  UserUpdatePayload,
} from '@/types/api'

export type PaginationParams = {
  page?: number
  page_size?: number
}

export async function getHealth() {
  const { data } = await http.get<ApiResponse<HealthData>>('/health')
  return data.data
}

export async function getAuthStatus() {
  const { data } = await http.get<ApiResponse<AuthStatusData>>('/api/v1/auth/status')
  return data.data
}

export async function login(payload: AuthLoginPayload) {
  const { data } = await http.post<ApiResponse<AuthLoginData>>('/api/v1/auth/login', payload)
  return data.data
}

export async function logout() {
  const { data } = await http.post<ApiResponse<{ status: string }>>('/api/v1/auth/logout')
  return data.data
}

export async function getCurrentUser() {
  const { data } = await http.get<ApiResponse<UserItem>>('/api/v1/auth/me')
  return data.data
}

export async function changeMyPassword(payload: AuthChangePasswordPayload) {
  const { data } = await http.post<ApiResponse<{ status: string; reauth_required: boolean }>>('/api/v1/auth/change-password', payload)
  return data.data
}

export async function submitConversation(payload: ConversationPayload) {
  const { data } = await http.post<ApiResponse<ConversationData>>('/api/v1/conversations', payload)
  return data.data
}

export async function streamConversation(
  payload: ConversationPayload,
  handlers: {
    onMeta?: (data: ConversationStreamMetaData) => void
    onDelta?: (data: ConversationStreamDeltaData) => void
    onDone?: (data: ConversationStreamDoneData) => void
    onError?: (data: { error: string }) => void
    onConversationMessage?: (data: { conversation_id: string; type: string; content: string }) => void
    onConversationInput?: (data: { conversation_id: string; question: string; input_type: string; options?: string[]; placeholder?: string }) => void
  },
  signal?: AbortSignal,
) {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/chats/stream`, {
    method: 'POST',
    signal,
    headers: {
      'Content-Type': 'application/json',
      Authorization: getAuthToken() ? `Bearer ${getAuthToken()}` : '',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok || !response.body) {
    const message = await response.text()
    throw new Error(message || `HTTP ${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let currentEvent = ''
  let dataLines: string[] = []

  const flushEvent = () => {
    const data = dataLines.join('\n').trim()
    dataLines = []
    if (!data) {
      currentEvent = ''
      return
    }

    const parsed = JSON.parse(data)
    if (currentEvent === 'conversation.meta') {
      handlers.onMeta?.(parsed as ConversationStreamMetaData)
    } else if (currentEvent === 'conversation.delta') {
      handlers.onDelta?.(parsed as ConversationStreamDeltaData)
    } else if (currentEvent === 'conversation.done') {
      handlers.onDone?.(parsed as ConversationStreamDoneData)
    } else if (currentEvent === 'conversation.error') {
      handlers.onError?.(parsed as { error: string })
    } else if (currentEvent === 'conversation.message') {
      handlers.onConversationMessage?.(parsed as { conversation_id: string; type: string; content: string })
    } else if (currentEvent === 'conversation.input') {
      handlers.onConversationInput?.(parsed as { conversation_id: string; question: string; input_type: string; options?: string[]; placeholder?: string })
    }
    currentEvent = ''
  }

  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })

    let boundaryIndex = buffer.indexOf('\n')
    while (boundaryIndex >= 0) {
      const line = buffer.slice(0, boundaryIndex).replace(/\r$/, '')
      buffer = buffer.slice(boundaryIndex + 1)

      if (!line.trim()) {
        flushEvent()
      } else if (line.startsWith('event:')) {
        currentEvent = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trim())
      }

      boundaryIndex = buffer.indexOf('\n')
    }

    if (done) {
      if (buffer.trim()) {
        const finalLine = buffer.replace(/\r$/, '')
        if (finalLine.startsWith('data:')) {
          dataLines.push(finalLine.slice(5).trim())
        }
      }
      flushEvent()
      break
    }
  }
}

export async function getConversations(params?: PaginationParams) {
  const { data } = await http.get<ApiResponse<ConversationListData>>('/api/v1/chats', { params })
  return data.data
}

export async function getConversationMessages(conversationId: string) {
  const { data } = await http.get<ApiResponse<ConversationMessagesData>>(`/api/v1/chats/${conversationId}/messages`)
  return data.data
}

export async function deleteConversation(conversationId: string) {
  const { data } = await http.delete<ApiResponse<{ conversation_id: string; status: string }>>(`/api/v1/chats/${conversationId}`)
  return data.data
}

export interface ChatItem {
  id: string
  title: string | null
  node_id: string
  model_id: string | null
  model_name: string | null
  status: string
  summary: string
  created_at: string | null
  updated_at: string | null
}

export interface ChatListData {
  items: ChatItem[]
  total: number
  page: number
  page_size: number
}

export interface ChatMessage {
  id: string
  chat_id: string
  role: string
  type: string
  content: string
  metadata: Record<string, unknown>
  created_at: string | null
}

export interface ChatMessagesData {
  chat_id: string
  items: ChatMessage[]
  total: number
  page: number
  page_size: number
}

export interface ChatCreatePayload {
  chat_id?: string
  node_id?: string
  model_id?: string
  message: string
}

export async function getChats(params?: PaginationParams) {
  const { data } = await http.get<ApiResponse<ChatListData>>('/api/v1/chats', { params })
  return data.data
}

export async function getChat(chatId: string) {
  const { data } = await http.get<ApiResponse<ChatItem>>(`/api/v1/chats/${chatId}`)
  return data.data
}

export async function createChat(payload: ChatCreatePayload) {
  const { data } = await http.post<ApiResponse<{ chat_id: string; title: string; model_id: string; model_name: string }>>('/api/v1/chats', payload)
  return data.data
}

export async function deleteChat(chatId: string) {
  const { data } = await http.delete<ApiResponse<{ chat_id: string; status: string }>>(`/api/v1/chats/${chatId}`)
  return data.data
}

export async function getChatMessages(chatId: string, params?: PaginationParams) {
  const { data } = await http.get<ApiResponse<ChatMessagesData>>(`/api/v1/chats/${chatId}/messages`, { params })
  return data.data
}

export function buildChatStreamUrl(chatId: string, message: string) {
  const baseUrl = getApiBaseUrl().trim()
  const eventPath = `/api/v1/chats/${chatId}/stream`
  const url = baseUrl ? new URL(eventPath, baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`) : new URL(eventPath, window.location.origin)
  url.searchParams.set('message', message)
  const token = getAuthToken()
  if (token) {
    url.searchParams.set('access_token', token)
  }
  return url.toString()
}

export async function streamChat(
  payload: ChatCreatePayload,
  handlers: {
    onMeta?: (data: ConversationStreamMetaData) => void
    onDelta?: (data: ConversationStreamDeltaData) => void
    onReasoning?: (data: { conversation_id: string; delta: string }) => void
    onReasoningDone?: (data: { conversation_id: string; duration: number }) => void
    onDone?: (data: ConversationStreamDoneData) => void
    onError?: (data: { error: string }) => void
    onConversationMessage?: (data: { conversation_id: string; type: string; content: string }) => void
    onConversationInput?: (data: { conversation_id: string; question: string; input_type: string; options?: string[]; placeholder?: string }) => void
  },
  signal?: AbortSignal,
) {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/chats/stream`, {
    method: 'POST',
    signal,
    headers: {
      'Content-Type': 'application/json',
      Authorization: getAuthToken() ? `Bearer ${getAuthToken()}` : '',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok || !response.body) {
    const message = await response.text()
    throw new Error(message || `HTTP ${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let currentEvent = ''
  let dataLines: string[] = []

  const flushEvent = () => {
    const data = dataLines.join('\n').trim()
    dataLines = []
    if (!data) {
      currentEvent = ''
      return
    }

    const parsed = JSON.parse(data)
    if (currentEvent === 'conversation.meta') {
      handlers.onMeta?.(parsed as ConversationStreamMetaData)
    } else if (currentEvent === 'conversation.delta') {
      handlers.onDelta?.(parsed as ConversationStreamDeltaData)
    } else if (currentEvent === 'conversation.reasoning') {
      handlers.onReasoning?.(parsed as { conversation_id: string; delta: string })
    } else if (currentEvent === 'conversation.reasoning_done') {
      handlers.onReasoningDone?.(parsed as { conversation_id: string; duration: number })
    } else if (currentEvent === 'conversation.done') {
      handlers.onDone?.(parsed as ConversationStreamDoneData)
    } else if (currentEvent === 'conversation.error') {
      handlers.onError?.(parsed as { error: string })
    } else if (currentEvent === 'conversation.message') {
      handlers.onConversationMessage?.(parsed as { conversation_id: string; type: string; content: string })
    } else if (currentEvent === 'conversation.input') {
      handlers.onConversationInput?.(parsed as { conversation_id: string; question: string; input_type: string; options?: string[]; placeholder?: string })
    }
    currentEvent = ''
  }

  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })

    let boundaryIndex = buffer.indexOf('\n')
    while (boundaryIndex >= 0) {
      const line = buffer.slice(0, boundaryIndex).replace(/\r$/, '')
      buffer = buffer.slice(boundaryIndex + 1)

      if (!line.trim()) {
        flushEvent()
      } else if (line.startsWith('event:')) {
        currentEvent = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trim())
      }

      boundaryIndex = buffer.indexOf('\n')
    }

    if (done) {
      if (buffer.trim()) {
        const finalLine = buffer.replace(/\r$/, '')
        if (finalLine.startsWith('data:')) {
          dataLines.push(finalLine.slice(5).trim())
        }
      }
      flushEvent()
      break
    }
  }
}

export async function getTasks(params?: PaginationParams) {
  const { data } = await http.get<ApiResponse<ExecuteListData>>('/api/v1/tasks', { params })
  return data.data
}

export async function getTaskDetail(taskId: string) {
  const { data } = await http.get<ApiResponse<ExecuteDetail>>(`/api/v1/tasks/${taskId}`)
  return data.data
}

export async function confirmTask(taskId: string, payload: ExecuteConfirmPayload) {
  const { data } = await http.post<ApiResponse<ExecuteDetail>>(`/api/v1/tasks/${taskId}/confirm`, payload)
  return data.data
}

export async function stopTask(taskId: string) {
  const { data } = await http.post<ApiResponse<ExecuteDetail>>(`/api/v1/tasks/${taskId}/stop`)
  return data.data
}

export async function restartTask(taskId: string) {
  const { data } = await http.post<ApiResponse<ExecuteDetail>>(`/api/v1/tasks/${taskId}/restart`)
  return data.data
}

export async function deleteTask(taskId: string) {
  const { data } = await http.delete<ApiResponse<{ task_id: string; status: string }>>(`/api/v1/tasks/${taskId}`)
  return data.data
}

export async function provideTaskInput(taskId: string, payload: ExecuteInputPayload) {
  const { data } = await http.post<ApiResponse<ExecuteDetail>>(`/api/v1/tasks/${taskId}/input`, payload)
  return data.data
}

export function buildTaskContinueUrl(taskId: string) {
  const baseUrl = getApiBaseUrl().trim()
  const eventPath = `/api/v1/tasks/${taskId}/continue`
  const url = baseUrl ? new URL(eventPath, baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`) : new URL(eventPath, window.location.origin)
  const token = getAuthToken()
  if (token) {
    url.searchParams.set('access_token', token)
  }
  return url.toString()
}

export async function getModels(params?: PaginationParams) {
  const { data } = await http.get<ApiResponse<ModelConfigListData>>('/api/v1/settings/models', { params })
  return data.data
}

export async function confirmConversationExecute(conversationId: string, payload: ExecuteConfirmPayload) {
  const { data } = await http.post<ApiResponse<ExecuteDetail>>(`/api/v1/chats/${conversationId}/confirm`, payload)
  return data.data
}

export async function stopConversationExecute(conversationId: string) {
  const { data } = await http.post<ApiResponse<ExecuteDetail>>(`/api/v1/chats/${conversationId}/stop`)
  return data.data
}

export async function restartConversationExecute(conversationId: string) {
  const { data } = await http.post<ApiResponse<ExecuteDetail>>(`/api/v1/chats/${conversationId}/restart`)
  return data.data
}

export async function provideConversationInput(conversationId: string, payload: ExecuteInputPayload) {
  const { data } = await http.post<ApiResponse<ExecuteDetail>>(`/api/v1/chats/${conversationId}/input`, payload)
  return data.data
}

export function buildConversationContinueUrl(conversationId: string) {
  const baseUrl = getApiBaseUrl().trim()
  const eventPath = `/api/v1/chats/${conversationId}/continue`
  const url = baseUrl ? new URL(eventPath, baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`) : new URL(eventPath, window.location.origin)
  const token = getAuthToken()
  if (token) {
    url.searchParams.set('access_token', token)
  }
  return url.toString()
}

export async function getModel(modelId: string) {
  const { data } = await http.get<ApiResponse<ModelConfigItem>>(`/api/v1/settings/models/${modelId}`)
  return data.data
}

export async function createModel(payload: ModelConfigPayload) {
  const { data } = await http.post<ApiResponse<ModelConfigItem>>('/api/v1/settings/models', payload)
  return data.data
}

export async function updateModel(modelId: string, payload: Partial<ModelConfigPayload>) {
  const { data } = await http.put<ApiResponse<ModelConfigItem>>(`/api/v1/settings/models/${modelId}`, payload)
  return data.data
}

export async function deleteModel(modelId: string) {
  const { data } = await http.delete<ApiResponse<null>>(`/api/v1/settings/models/${modelId}`)
  return data.data
}

export async function setDefaultModel(modelId: string) {
  const { data } = await http.post<ApiResponse<null>>(`/api/v1/settings/models/${modelId}/default`)
  return data.data
}

export async function getGlobalSettings() {
  const { data } = await http.get<ApiResponse<GlobalSettingsData>>('/api/v1/settings/global')
  return data.data
}

export async function updateGlobalSettings(payload: GlobalSettingsPayload) {
  const { data } = await http.put<ApiResponse<GlobalSettingsData>>('/api/v1/settings/global', payload)
  return data.data
}

export async function getAuthSettings() {
  const { data } = await http.get<ApiResponse<AuthSettingsData>>('/api/v1/settings/auth')
  return data.data
}

export async function updateAuthSettings(payload: AuthSettingsPayload) {
  const { data } = await http.put<ApiResponse<AuthSettingsData>>('/api/v1/settings/auth', payload)
  return data.data
}

export async function getNodes(params?: PaginationParams) {
  const { data } = await http.get<ApiResponse<NodeListData>>('/api/v1/nodes', { params })
  return data.data
}

export async function createNode(payload: NodePayload) {
  const { data } = await http.post<ApiResponse<NodeItem>>('/api/v1/nodes', payload)
  return data.data
}

export async function updateNode(nodeId: string, payload: NodePayload) {
  const { data } = await http.put<ApiResponse<NodeItem>>(`/api/v1/nodes/${nodeId}`, payload)
  return data.data
}

export async function deleteNode(nodeId: string) {
  const { data } = await http.delete<ApiResponse<null>>(`/api/v1/nodes/${nodeId}`)
  return data.data
}

export async function getUsers(params?: PaginationParams) {
  const { data } = await http.get<ApiResponse<UserListData>>('/api/v1/users', { params })
  return data.data
}

export async function createUser(payload: UserPayload) {
  const { data } = await http.post<ApiResponse<UserItem>>('/api/v1/users', payload)
  return data.data
}

export async function updateUser(userId: string, payload: UserUpdatePayload) {
  const { data } = await http.put<ApiResponse<UserItem>>(`/api/v1/users/${userId}`, payload)
  return data.data
}

export async function deleteUser(userId: string) {
  const { data } = await http.delete<ApiResponse<{ user_id: string; status: string }>>(`/api/v1/users/${userId}`)
  return data.data
}

export async function resetUserPassword(userId: string, payload: UserResetPasswordPayload) {
  const { data } = await http.post<ApiResponse<{ user_id: string; status: string; reauth_required: boolean }>>(`/api/v1/users/${userId}/reset-password`, payload)
  return data.data
}

export async function executeTerminalCommand(payload: TerminalExecutePayload) {
  const { data } = await http.post<ApiResponse<TerminalExecuteData>>('/api/v1/terminal/execute', payload)
  return data.data
}
