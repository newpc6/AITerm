export interface ToolParameter {
  type: string
  description: string
  enum?: string[]
  default?: unknown
}

export interface ToolParameters {
  type: 'object'
  properties: Record<string, ToolParameter>
  required: string[]
}

export interface ToolConfigField {
  name: string
  display_name: string
  type: string
  description: string
  default?: string
  required: boolean
}

export interface ToolConfigSchema {
  fields: ToolConfigField[]
}

export interface Tool {
  id: string
  name: string
  display_name?: string
  description?: string
  code: string
  parameters?: ToolParameters
  config_schema?: ToolConfigSchema
  enabled: boolean
  created_at?: string
  updated_at?: string
}

export interface ToolCreate {
  name: string
  display_name?: string
  description?: string
  code: string
  parameters?: ToolParameters
  config_schema?: ToolConfigSchema
  enabled: boolean
}

export interface ToolUpdate {
  name?: string
  display_name?: string
  description?: string
  code?: string
  parameters?: ToolParameters
  config_schema?: ToolConfigSchema
  enabled?: boolean
}

export interface ToolExecuteResult {
  success: boolean
  result?: unknown
  error?: string
}

export interface OpenAITool {
  type: 'function'
  function: {
    name: string
    description: string
    parameters: ToolParameters
  }
}
