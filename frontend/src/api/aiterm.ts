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
  PaginatedData,
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
  created_at: string | null
  metadata?: {
    question?: string
    input_type?: string
    options?: string[]
    placeholder?: string
    [key: string]: unknown
  }
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
    onReasoningStart?: (data: { chat_id: string; iteration?: number; timestamp: string }) => void
    onReasoning?: (data: { chat_id: string; iteration?: number; delta: string }) => void
    onReasoningDone?: (data: { chat_id: string; iteration?: number; duration: number }) => void
    onIterationStart?: (data: { chat_id: string; iteration: number; input: string; full_input?: string }) => void
    onToolCall?: (data: { chat_id: string; iteration?: number; name: string; arguments: string; result: string; timestamp?: string }) => void
    onDone?: (data: ConversationStreamDoneData) => void
    onError?: (data: { error: string }) => void
    onConversationMessage?: (data: { chat_id: string; type: string; content: string }) => void
    onConversationInput?: (data: { chat_id: string; question: string; input_type: string; options?: string[]; placeholder?: string }) => void
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
    } else if (currentEvent === 'conversation.reasoning_start') {
      handlers.onReasoningStart?.(parsed as { chat_id: string; iteration?: number; timestamp: string })
    } else if (currentEvent === 'conversation.reasoning') {
      handlers.onReasoning?.(parsed as { chat_id: string; iteration?: number; delta: string })
    } else if (currentEvent === 'conversation.reasoning_done') {
      handlers.onReasoningDone?.(parsed as { chat_id: string; iteration?: number; duration: number })
    } else if (currentEvent === 'conversation.iteration_start') {
      handlers.onIterationStart?.(parsed as { chat_id: string; iteration: number; input: string })
    } else if (currentEvent === 'conversation.tool_call') {
      handlers.onToolCall?.(parsed as { chat_id: string; iteration?: number; name: string; arguments: string; result: string; timestamp?: string })
    } else if (currentEvent === 'conversation.done') {
      handlers.onDone?.(parsed as ConversationStreamDoneData)
    } else if (currentEvent === 'conversation.error') {
      handlers.onError?.(parsed as { error: string })
    } else if (currentEvent === 'conversation.message') {
      handlers.onConversationMessage?.(parsed as { chat_id: string; type: string; content: string })
    } else if (currentEvent === 'conversation.input') {
      handlers.onConversationInput?.(parsed as { chat_id: string; question: string; input_type: string; options?: string[]; placeholder?: string })
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

export async function selectFolder() {
  const { data } = await http.post<ApiResponse<{ path: string | null }>>('/api/v1/settings/select-folder')
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

export async function getTools(enabledOnly = false) {
  const { data } = await http.get<ApiResponse<import('@/types/tool').Tool[]>>('/api/v1/tools', {
    params: { enabled_only: enabledOnly },
  })
  return data.data
}

export async function getTool(toolId: string) {
  const { data } = await http.get<ApiResponse<import('@/types/tool').Tool>>(`/api/v1/tools/${toolId}`)
  return data.data
}

export async function createTool(payload: import('@/types/tool').ToolCreate) {
  const { data } = await http.post<ApiResponse<import('@/types/tool').Tool>>('/api/v1/tools', payload)
  return data.data
}

export async function updateTool(toolId: string, payload: import('@/types/tool').ToolUpdate) {
  const { data } = await http.put<ApiResponse<import('@/types/tool').Tool>>(`/api/v1/tools/${toolId}`, payload)
  return data.data
}

export async function deleteTool(toolId: string) {
  const { data } = await http.delete<ApiResponse<boolean>>(`/api/v1/tools/${toolId}`)
  return data.data
}

export async function exportTools(toolIds?: string[]) {
  const { data } = await http.post<ApiResponse<import('@/types/tool').ToolExport[]>>('/api/v1/tools/export', toolIds)
  return data.data
}

export async function importTools(payload: { file?: File; json_content?: string; overwrite?: boolean }) {
  const formData = new FormData()
  if (payload.file) {
    formData.append('file', payload.file)
  }
  if (payload.json_content) {
    formData.append('json_content', payload.json_content)
  }
  formData.append('overwrite', String(payload.overwrite || false))

  const { data } = await http.post<ApiResponse<import('@/types/tool').ToolsImportResponse>>('/api/v1/tools/import', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return data.data
}

export async function getBuiltinTools() {
  const { data } = await http.get<ApiResponse<import('@/types/tool').BuiltinTool[]>>('/api/v1/tools/builtin/list')
  return data.data
}

export async function importBuiltinTools(filenames: string[], overwrite = false) {
  const { data } = await http.post<ApiResponse<import('@/types/tool').ToolsImportResponse>>('/api/v1/tools/builtin/import', filenames, {
    params: { overwrite },
  })
  return data.data
}

export async function executeTool(toolId: string, arguments_: Record<string, unknown>) {
  const { data } = await http.post<ApiResponse<import('@/types/tool').ToolExecuteResult>>(`/api/v1/tools/${toolId}/execute`, { arguments: arguments_ })
  return data.data
}

export async function getOpenAIToolsSchema() {
  const { data } = await http.get<ApiResponse<import('@/types/tool').OpenAITool[]>>('/api/v1/tools/schema/openai')
  return data.data
}

export interface FileItem {
  id: string
  uuid: string
  filename: string
  original_filename: string
  file_size: number
  file_type: string | null
  mime_type: string | null
  source: string
  chat_id: string | null
  message_id: string | null
  description: string | null
  is_deleted: boolean
  created_at: string | null
  updated_at: string | null
}

export interface FileListData {
  files: FileItem[]
  total: number
}

export interface FileUploadPayload {
  file: File
  chat_id?: string
  message_id?: string
  description?: string
}

export async function getFiles(params?: PaginationParams & { search?: string; file_type?: string; source?: string }) {
  const { data } = await http.get<ApiResponse<FileListData>>('/api/v1/files', { params })
  return data.data
}

export async function getFile(fileId: string) {
  const { data } = await http.get<ApiResponse<FileItem>>(`/api/v1/files/${fileId}`)
  return data.data
}

export function getFileDownloadUrl(fileUuid: string) {
  return `${getApiBaseUrl()}/api/v1/files/download/${fileUuid}`
}

export async function uploadFile(payload: FileUploadPayload) {
  const formData = new FormData()
  formData.append('file', payload.file)
  if (payload.chat_id) {
    formData.append('chat_id', payload.chat_id)
  }
  if (payload.message_id) {
    formData.append('message_id', payload.message_id)
  }
  if (payload.description) {
    formData.append('description', payload.description)
  }

  const { data } = await http.post<ApiResponse<FileItem>>('/api/v1/files/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return data.data
}

export async function deleteFile(fileId: string) {
  const { data } = await http.delete<ApiResponse<boolean>>(`/api/v1/files/${fileId}`)
  return data.data
}

export async function batchDeleteFiles(ids: string[]) {
  const { data } = await http.post<ApiResponse<number>>('/api/v1/files/batch-delete', { ids })
  return data.data
}

export async function getFileTypes() {
  const { data } = await http.get<ApiResponse<string[]>>('/api/v1/files/types/list')
  return data.data
}

export async function getFileSources() {
  const { data } = await http.get<ApiResponse<string[]>>('/api/v1/files/sources/list')
  return data.data
}

export interface ShareItem {
  id: string
  share_id: string
  chat_id: string
  title: string
  has_password: boolean
  expires_at: string | null
  view_count: number
  created_at: string | null
  show_input: boolean
  show_thinking: boolean
  show_tools: boolean
  show_answer: boolean
}

export interface ShareCreatePayload {
  chat_id: string
  title?: string
  password?: string
  expires_in?: number
  show_input?: boolean
  show_thinking?: boolean
  show_tools?: boolean
  show_answer?: boolean
}

export interface ShareVerifyPayload {
  share_id: string
  password?: string
}

export interface ShareDetailData {
  share_id: string
  title: string
  has_password: boolean
  expires_at: string | null
  messages: Array<{
    id: string
    role: string
    type: string
    content: string
    created_at: string | null
  }>
  chat_title: string | null
  created_at: string | null
  show_input: boolean
  show_thinking: boolean
  show_tools: boolean
  show_answer: boolean
}

export async function createShare(payload: ShareCreatePayload) {
  const { data } = await http.post<ApiResponse<ShareItem>>('/api/v1/shares', payload)
  return data.data
}

export async function getShare(shareId: string) {
  const { data } = await http.get<ApiResponse<ShareItem>>(`/api/v1/shares/${shareId}`)
  return data.data
}

export async function getShareByChat(chatId: string) {
  const { data } = await http.get<ApiResponse<ShareItem>>(`/api/v1/shares/chat/${chatId}`)
  return data.data
}

export async function deleteShare(shareId: string) {
  const { data } = await http.delete<ApiResponse<{ share_id: string; status: string }>>(`/api/v1/shares/${shareId}`)
  return data.data
}

export async function deleteShareByChat(chatId: string) {
  const { data } = await http.delete<ApiResponse<{ chat_id: string; status: string }>>(`/api/v1/shares/chat/${chatId}`)
  return data.data
}

export async function verifyShare(shareId: string, payload: ShareVerifyPayload) {
  const { data } = await http.post<ApiResponse<ShareDetailData>>(`/api/v1/shares/${shareId}/verify`, payload)
  return data.data
}

export async function getSharePreview(shareId: string) {
  const { data } = await http.get<
    ApiResponse<{
      share_id: string
      title: string
      has_password: boolean
      expires_at: string | null
      created_at: string | null
    }>
  >(`/api/v1/shares/${shareId}/preview`)
  return data.data
}

export async function listShares(page: number = 1, pageSize: number = 20) {
  const { data } = await http.get<ApiResponse<PaginatedData<ShareItem>>>('/api/v1/shares', {
    params: { page, page_size: pageSize },
  })
  return data.data
}

export async function batchDeleteShares(shareIds: string[]) {
  const { data } = await http.post<ApiResponse<{ deleted_count: number }>>('/api/v1/shares/batch-delete', shareIds)
  return data.data
}
