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
  LLMPublicInfo,
  LLMSettingsData,
  LLMSettingsPayload,
  NodeItem,
  NodeListData,
  NodePayload,
  TaskConfirmPayload,
  TaskDetail,
  TaskListData,
  TerminalExecuteData,
  TerminalExecutePayload,
  UserItem,
  UserListData,
  UserPayload,
  UserResetPasswordPayload,
  UserUpdatePayload,
} from '@/types/api'

export async function getHealth() {
  const { data } = await http.get<ApiResponse<HealthData>>('/health')
  return data.data
}

export async function getAuthStatus() {
  const { data } = await http.get<ApiResponse<AuthStatusData>>('/api/auth/status')
  return data.data
}

export async function login(payload: AuthLoginPayload) {
  const { data } = await http.post<ApiResponse<AuthLoginData>>('/api/auth/login', payload)
  return data.data
}

export async function logout() {
  const { data } = await http.post<ApiResponse<{ status: string }>>('/api/auth/logout')
  return data.data
}

export async function getCurrentUser() {
  const { data } = await http.get<ApiResponse<UserItem>>('/api/auth/me')
  return data.data
}

export async function changeMyPassword(payload: AuthChangePasswordPayload) {
  const { data } = await http.post<ApiResponse<{ status: string; reauth_required: boolean }>>('/api/auth/change-password', payload)
  return data.data
}

export async function submitConversation(payload: ConversationPayload) {
  const { data } = await http.post<ApiResponse<ConversationData>>('/api/conversations', payload)
  return data.data
}

export async function streamConversation(
  payload: ConversationPayload,
  handlers: {
    onMeta?: (data: ConversationStreamMetaData) => void
    onDelta?: (data: ConversationStreamDeltaData) => void
    onDone?: (data: ConversationStreamDoneData) => void
  },
  signal?: AbortSignal,
) {
  const response = await fetch(`${getApiBaseUrl()}/api/conversations/stream`, {
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

    const parsed = JSON.parse(data) as ConversationStreamMetaData | ConversationStreamDeltaData | ConversationStreamDoneData
    if (currentEvent === 'conversation.meta') {
      handlers.onMeta?.(parsed as ConversationStreamMetaData)
    } else if (currentEvent === 'conversation.delta') {
      handlers.onDelta?.(parsed as ConversationStreamDeltaData)
    } else if (currentEvent === 'conversation.done') {
      handlers.onDone?.(parsed as ConversationStreamDoneData)
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

export async function getConversations() {
  const { data } = await http.get<ApiResponse<ConversationListData>>('/api/conversations')
  return data.data
}

export async function getConversationMessages(conversationId: string) {
  const { data } = await http.get<ApiResponse<ConversationMessagesData>>(`/api/conversations/${conversationId}/messages`)
  return data.data
}

export async function deleteConversation(conversationId: string) {
  const { data } = await http.delete<ApiResponse<{ conversation_id: string; status: string }>>(`/api/conversations/${conversationId}`)
  return data.data
}

export async function getTasks() {
  const { data } = await http.get<ApiResponse<TaskListData>>('/api/tasks')
  return data.data
}

export async function getTaskDetail(taskId: string) {
  const { data } = await http.get<ApiResponse<TaskDetail>>(`/api/tasks/${taskId}`)
  return data.data
}

export async function confirmTask(taskId: string, payload: TaskConfirmPayload) {
  const { data } = await http.post<ApiResponse<TaskDetail>>(`/api/tasks/${taskId}/confirm`, payload)
  return data.data
}

export async function stopTask(taskId: string) {
  const { data } = await http.post<ApiResponse<TaskDetail>>(`/api/tasks/${taskId}/stop`)
  return data.data
}

export async function restartTask(taskId: string) {
  const { data } = await http.post<ApiResponse<TaskDetail>>(`/api/tasks/${taskId}/restart`)
  return data.data
}

export async function deleteTask(taskId: string) {
  const { data } = await http.delete<ApiResponse<{ task_id: string; status: string }>>(`/api/tasks/${taskId}`)
  return data.data
}

export async function getLLMSettings() {
  const { data } = await http.get<ApiResponse<LLMSettingsData>>('/api/settings/llm')
  return data.data
}

export async function getLLMPublicInfo() {
  const { data } = await http.get<ApiResponse<LLMPublicInfo>>('/api/settings/llm/public')
  return data.data
}

export async function updateLLMSettings(payload: LLMSettingsPayload) {
  const { data } = await http.put<ApiResponse<LLMSettingsData>>('/api/settings/llm', payload)
  return data.data
}

export async function getAuthSettings() {
  const { data } = await http.get<ApiResponse<AuthSettingsData>>('/api/settings/auth')
  return data.data
}

export async function updateAuthSettings(payload: AuthSettingsPayload) {
  const { data } = await http.put<ApiResponse<AuthSettingsData>>('/api/settings/auth', payload)
  return data.data
}

export async function getNodes() {
  const { data } = await http.get<ApiResponse<NodeListData>>('/api/nodes')
  return data.data
}

export async function createNode(payload: NodePayload) {
  const { data } = await http.post<ApiResponse<NodeItem>>('/api/nodes', payload)
  return data.data
}

export async function updateNode(nodeId: string, payload: NodePayload) {
  const { data } = await http.put<ApiResponse<NodeItem>>(`/api/nodes/${nodeId}`, payload)
  return data.data
}

export async function deleteNode(nodeId: string) {
  const { data } = await http.delete<ApiResponse<null>>(`/api/nodes/${nodeId}`)
  return data.data
}

export async function getUsers() {
  const { data } = await http.get<ApiResponse<UserListData>>('/api/users')
  return data.data
}

export async function createUser(payload: UserPayload) {
  const { data } = await http.post<ApiResponse<UserItem>>('/api/users', payload)
  return data.data
}

export async function updateUser(userId: string, payload: UserUpdatePayload) {
  const { data } = await http.put<ApiResponse<UserItem>>(`/api/users/${userId}`, payload)
  return data.data
}

export async function deleteUser(userId: string) {
  const { data } = await http.delete<ApiResponse<{ user_id: string; status: string }>>(`/api/users/${userId}`)
  return data.data
}

export async function resetUserPassword(userId: string, payload: UserResetPasswordPayload) {
  const { data } = await http.post<ApiResponse<{ user_id: string; status: string; reauth_required: boolean }>>(`/api/users/${userId}/reset-password`, payload)
  return data.data
}

export async function executeTerminalCommand(payload: TerminalExecutePayload) {
  const { data } = await http.post<ApiResponse<TerminalExecuteData>>('/api/terminal/execute', payload)
  return data.data
}
