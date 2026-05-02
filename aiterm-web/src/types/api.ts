export type ConversationMode = 'chat' | 'task'

export type ApiResponse<T> = {
  code: number
  message: string
  data: T
}

export type PaginatedData<T> = {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
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
  model_id?: string
  message: string
  mode: ConversationMode
  task_id?: string
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
}

export type ConversationListItem = {
  id: string
  title: string
  last_message: string
  message_count: number
  latest_node_id?: string
  latest_status?: string
  updated_at: string
}

export type ChatItem = {
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

export type ConversationListData = PaginatedData<ConversationListItem>

export type TaskItem = {
  id: string
  title: string
  status: string
  progress: number
  conversation_id: string
  node_id: string
  model_id?: string
  model_name?: string
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

export type TaskInputRequest = {
  question: string
  input_type: 'text' | 'select' | 'multiselect'
  options: string[]
  placeholder: string
  default_value: string
}

export type TaskDetail = {
  id: string
  title: string
  status: string
  progress: number
  conversation_id: string
  node_id: string
  model_id?: string
  model_name?: string
  pending_command?: string
  risk_reason?: string
  summary: string
  final_result?: string
  steps: TaskDetailStep[]
  input_question?: string
  input_type?: 'text' | 'select' | 'multiselect'
  input_options?: string[]
  input_placeholder?: string
  user_input?: string
  created_at: string
  updated_at: string
}

export type TaskInputPayload = {
  user_input: string
}

export type TaskConfirmPayload = {
  approved: boolean
}

export type TaskListData = PaginatedData<TaskItem>

export type ModelConfigItem = {
  id: string
  name: string
  api_url: string
  api_key: string
  model: string
  temperature: number
  extra_params: Record<string, unknown>
  extra_body: Record<string, unknown>
  extra_headers: Record<string, string>
  is_default: boolean
  created_at: string
  updated_at: string
}

export type ModelConfigListData = PaginatedData<ModelConfigItem>

export type ModelConfigPayload = {
  name: string
  api_url: string
  api_key: string
  model: string
  temperature: number
  extra_params: Record<string, unknown>
  extra_body: Record<string, unknown>
  extra_headers: Record<string, string>
  is_default: boolean
}

export type GlobalSettingsData = {
  intent_detection_prompt: string
  chat_system_prompt: string
  chat_history_limit: number
  execution_planner_prompt: string
  execution_planner_user_prompt: string
  execution_windows_tool_prompt: string
  execution_linux_tool_prompt: string
  execution_mac_tool_prompt: string
  execution_failure_repair_prompt: string
  execution_command_rules_prompt: string
  execution_command_blacklist: string[]
  execution_command_whitelist: string[]
}

export type GlobalSettingsPayload = {
  intent_detection_prompt?: string
  chat_system_prompt?: string
  chat_history_limit?: number
  execution_planner_prompt?: string
  execution_planner_user_prompt?: string
  execution_windows_tool_prompt?: string
  execution_linux_tool_prompt?: string
  execution_mac_tool_prompt?: string
  execution_failure_repair_prompt?: string
  execution_command_rules_prompt?: string
  execution_command_blacklist?: string[]
  execution_command_whitelist?: string[]
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

export type UserListData = PaginatedData<UserItem>

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

export type NodeListData = PaginatedData<NodeItem>

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
