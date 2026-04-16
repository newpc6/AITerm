export type ConversationMode = 'chat' | 'task'

export type ApiResponse<T> = {
  code: number
  message: string
  data: T
}

export type HealthData = {
  status: string
  bootstrap?: {
    nodes_ready: boolean
    active_admin_count: number
    default_username: string
  }
}

export type ConversationPayload = {
  conversation_id: string
  node_id: string
  message: string
  mode: ConversationMode
}

export type ConversationData = {
  conversation_id: string
  reply: string
  task_id?: string
  mode: ConversationMode
}

export type ConversationStreamMetaData = {
  conversation_id: string
  mode: 'chat'
  node_id: string
}

export type ConversationStreamDeltaData = {
  conversation_id: string
  delta: string
}

export type ConversationStreamDoneData = {
  conversation_id: string
  reply: string
}

export type ConversationMessageItem = {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export type ConversationMessagesData = {
  conversation_id: string
  items: ConversationMessageItem[]
  latest_task_id?: string
}

export type ConversationListItem = {
  id: string
  title: string
  last_message: string
  message_count: number
  latest_task_id?: string
  latest_node_id?: string
  latest_status?: string
  updated_at: string
}

export type ConversationListData = {
  items: ConversationListItem[]
  total: number
}

export type TaskItem = {
  id: string
  title: string
  status: string
  progress: number
  conversation_id: string
  node_id: string
  pending_command?: string
  risk_reason?: string
  created_at: string
}

export type TaskDetailStep = {
  index: number
  title: string
  status: string
  command: string
  result_output?: string
  repair_count?: number
  original_command?: string
  first_failure_output?: string
  repaired_output?: string
  last_error?: string
  repair_reason?: string
  repair_suggestion?: string
  repaired_command?: string
}

export type TaskDetail = {
  id: string
  title: string
  status: string
  progress: number
  conversation_id: string
  node_id: string
  pending_command?: string
  risk_reason?: string
  summary: string
  final_result?: string
  steps: TaskDetailStep[]
  created_at: string
  updated_at: string
}

export type TaskConfirmPayload = {
  approved: boolean
}

export type TaskListData = {
  items: TaskItem[]
  total: number
  page: number
  page_size: number
}

export type LLMSettingsData = {
  api_url: string
  api_key: string
  model: string
  temperature: number
  chat_system_prompt: string
  task_planner_prompt: string
  task_planner_user_prompt: string
  task_windows_tool_prompt: string
  task_linux_tool_prompt: string
  task_mac_tool_prompt: string
  task_failure_repair_prompt: string
  task_command_rules_prompt: string
  task_command_blacklist: string[]
  task_command_whitelist: string[]
  configured: boolean
}

export type LLMPublicInfo = {
  model: string
  configured: boolean
}

export type LLMSettingsPayload = {
  api_url: string
  api_key: string
  model: string
  temperature: number
  chat_system_prompt: string
  task_planner_prompt: string
  task_planner_user_prompt: string
  task_windows_tool_prompt: string
  task_linux_tool_prompt: string
  task_mac_tool_prompt: string
  task_failure_repair_prompt: string
  task_command_rules_prompt: string
  task_command_blacklist: string[]
  task_command_whitelist: string[]
}

export type AuthSettingsData = {
  enabled: boolean
  allow_password_login: boolean
  session_ttl_hours: number
}

export type AuthSettingsPayload = AuthSettingsData

export type UserItem = {
  id: string
  username: string
  display_name: string
  role: string
  status: string
  last_login_at?: string
  created_at: string
  updated_at: string
}

export type UserPayload = {
  username: string
  display_name: string
  password: string
  role: string
  status: string
}

export type UserUpdatePayload = {
  display_name: string
  role: string
  status: string
}

export type UserListData = {
  items: UserItem[]
  total: number
}

export type AuthLoginPayload = {
  username: string
  password: string
}

export type AuthLoginData = {
  token: string
  expires_at: string
  user: UserItem
}

export type AuthChangePasswordPayload = {
  current_password: string
  new_password: string
}

export type UserResetPasswordPayload = {
  password: string
}

export type AuthStatusData = {
  enabled: boolean
  allow_password_login: boolean
  authenticated: boolean
  user?: UserItem
}

export type NodeItem = {
  id: string
  name: string
  host: string
  port: number
  status: string
}

export type NodeListData = {
  items: NodeItem[]
}

export type NodePayload = {
  name: string
  host: string
  port: number
}

export type TaskStreamStatusData = {
  task_id: string
  status: string
  progress: number
}

export type TaskStreamOutputData = {
  task_id: string
  stream: string
  content: string
}

export type TerminalExecutePayload = {
  command: string
  node_id?: string
}

export type TerminalExecuteData = {
  command: string
  output: string
  exit_code: number
  timed_out: boolean
  node_id: string
  node_name: string
  timestamp: string
}
