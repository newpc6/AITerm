export type MessageType =
  | "text"
  | "plan"
  | "step"
  | "step_result"
  | "approval"
  | "approved"
  | "rejected"
  | "input"
  | "input_response"
  | "output"
  | "error"
  | "summary"
  | "analysis"
  | "retry"

export type PlanStepMetadata = {
  index: number
  title: string
  command?: string
}

export type PlanMetadata = {
  steps: PlanStepMetadata[]
}

export type StepMetadata = {
  index: number
  title: string
  command: string
  status: string
}

export type StepResultMetadata = {
  index: number
  title: string
  command: string
  output?: string
  exit_code: number
  success: boolean
}

export type ApprovalMetadata = {
  commands: string[]
  reason: string
}

export type ApprovedMetadata = {
  commands: string[]
}

export type RejectedMetadata = {
  commands: string[]
  reason: string
}

export type InputMetadata = {
  question: string
  input_type: string
  options: string[]
  placeholder: string
}

export type InputResponseMetadata = {
  question: string
  answer: string
}

export type OutputMetadata = {
  command: string
  output?: string
  exit_code: number
}

export type ErrorMetadata = {
  message: string
  details?: string
}

export type AnalysisMetadata = {
  reason: string
  suggestion?: string
}

export type RetryMetadata = {
  index: number
  title: string
  old_command: string
  new_command: string
  reason: string
}

export type MessageMetadata =
  | PlanMetadata
  | StepMetadata
  | StepResultMetadata
  | ApprovalMetadata
  | ApprovedMetadata
  | RejectedMetadata
  | InputMetadata
  | InputResponseMetadata
  | OutputMetadata
  | ErrorMetadata
  | AnalysisMetadata
  | RetryMetadata
  | Record<string, unknown>

export type ChatMessage = {
  id: string
  role: "user" | "assistant"
  content: string
  type?: MessageType
  metadata?: MessageMetadata
  createdAt: string
}
