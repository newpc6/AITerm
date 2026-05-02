import type { ChatMessage } from '@/types/chat'

export type ExecuteStructuredMessage = {
  kind: 'plan' | 'step-start' | 'step-result' | 'summary' | 'repair' | 'info' | 'analyzing' | 'input-request' | 'approved' | 'output' | 'error' | 'analysis' | 'retry'
  title?: string
  stepLabel?: string
  body?: string
  command?: string
  question?: string
  options?: string[]
}

export type UserInputResponse = {
  question: string
  answer: string
}

export type StructuredInputResponse = {
  question: string
  inputType: 'text' | 'select' | 'multiselect'
  options: string[]
  answer: string
}

export function getMessageKind(message: ChatMessage): ExecuteStructuredMessage | null {
  if (message.type) {
    switch (message.type) {
      case 'plan':
        return { kind: 'plan', title: '步骤规划', body: message.content.replace(/^步骤规划\n?/, '') }
      case 'step':
        const stepMatch = message.content.match(/^开始执行第\s*(\d+)\s*步[:：]\s*(.+?)\n命令[:：]\s*([\s\S]+)$/)
        if (stepMatch) {
          return {
            kind: 'step-start',
            stepLabel: `第 ${stepMatch[1]} 步`,
            title: stepMatch[2].trim(),
            command: stepMatch[3].trim(),
          }
        }
        return { kind: 'step-start', title: '执行中', body: message.content }
      case 'step_result':
        return { kind: 'step-result', body: message.content }
      case 'output':
        return { kind: 'output', body: message.content }
      case 'error':
        return { kind: 'error', title: '错误', body: message.content }
      case 'summary':
        return { kind: 'summary', title: '总结', body: message.content }
      case 'analysis':
        return { kind: 'analysis', title: '分析', body: message.content }
      case 'retry':
        return { kind: 'retry', title: '重试', body: message.content }
      case 'approval':
        return { kind: 'info', title: '需要确认', body: message.content }
      case 'approved':
        return { kind: 'approved', title: '已批准', body: message.content.replace(/^已批准\n?/, '') }
      case 'rejected':
        return { kind: 'info', title: '已拒绝', body: message.content }
      case 'input':
        return { kind: 'input-request', question: message.content.replace(/^需要您的输入[:：]\s*/, '') }
      case 'input_response':
        return { kind: 'input-request', question: message.content }
      default:
        break
    }
  }
  return parseExecuteStructuredMessage(message.content)
}

export function parseUserInputResponse(content: string): UserInputResponse | null {
  const normalized = content.trim()
  if (!normalized) {
    return null
  }

  const match = normalized.match(/^用户输入[:：]\s*(.+)$/)
  if (match) {
    return {
      question: '',
      answer: match[1].trim(),
    }
  }

  return null
}

export function parseExecuteStructuredMessage(content: string): ExecuteStructuredMessage | null {
  const normalized = content.trim()
  if (!normalized) {
    return null
  }

  if (normalized.startsWith('步骤规划')) {
    const body = normalized.replace(/^步骤规划\n?/, '')
    return {
      kind: 'plan',
      title: '步骤规划',
      body: body,
    }
  }

  if (normalized.includes('正在') && normalized.includes('执行')) {
    return {
      kind: 'step-start',
      title: '执行中',
      body: normalized,
    }
  }

  if (normalized.startsWith('任务计划如下：')) {
    return {
      kind: 'plan',
      title: '执行计划',
      body: normalized.replace(/^任务计划如下：\s*/, ''),
    }
  }

  const stepStartMatch = normalized.match(/^开始执行第\s*(\d+)\s*步[:：]\s*(.+?)\n命令[:：]\s*([\s\S]+)$/)
  if (stepStartMatch) {
    return {
      kind: 'step-start',
      stepLabel: `第 ${stepStartMatch[1]} 步`,
      title: stepStartMatch[2].trim(),
      command: stepStartMatch[3].trim(),
    }
  }

  const stepResultMatch = normalized.match(/^第\s*(\d+)\s*步执行结果[:：]\s*\n?([\s\S]+)$/)
  if (stepResultMatch) {
    return {
      kind: 'step-result',
      stepLabel: `第 ${stepResultMatch[1]} 步结果`,
      body: stepResultMatch[2].trim(),
    }
  }

  if (normalized.startsWith('任务最终结果：')) {
    return {
      kind: 'summary',
      title: '最终结论',
      body: normalized.replace(/^任务最终结果：\s*/, ''),
    }
  }

  if (normalized.startsWith('失败复盘：') || normalized.includes('自动复盘')) {
    return {
      kind: 'repair',
      title: '自动复盘',
      body: normalized,
    }
  }

  if (normalized.includes('需要人工确认')) {
    return {
      kind: 'info',
      title: '操作确认',
      body: normalized,
    }
  }

  if (normalized.startsWith('已批准')) {
    const bodyMatch = normalized.match(/^已批准\n命令[:：]\s*([\s\S]+)$/)
    return {
      kind: 'approved',
      title: '已批准',
      body: bodyMatch ? bodyMatch[1].trim() : normalized.replace(/^已批准\n?/, ''),
    }
  }

  return null
}

export function parseStructuredInputResponse(content: string): StructuredInputResponse | null {
  if (!content.startsWith('[INPUT_RESPONSE]') || !content.includes('[/INPUT_RESPONSE]')) {
    return null
  }

  const questionMatch = content.match(/问题: (.+)/)
  const typeMatch = content.match(/类型: (.+)/)
  const optionsMatch = content.match(/选项: (.+)/)
  const answerMatch = content.match(/回答: (.+)/)

  const optionsStr = optionsMatch?.[1] || ''
  const options = optionsStr ? optionsStr.split('|||').filter(Boolean) : []
  const rawInputType = typeMatch?.[1] || 'text'
  const inputType: 'text' | 'select' | 'multiselect' = rawInputType === 'select' || rawInputType === 'multiselect' ? rawInputType : 'text'

  return {
    question: questionMatch?.[1] || '',
    inputType,
    options,
    answer: answerMatch?.[1] || '',
  }
}

export function isExecutePlanMessage(message: ChatMessage) {
  return message.role === 'assistant' && message.content.includes('任务计划如下') && message.content.includes('\n')
}

export function getExecutePlanIntro(content: string) {
  const parts = content.split('\n')
  return parts.shift()?.trim() ?? content.trim()
}

export function getExecutePlanCode(content: string) {
  const parts = content.split('\n')
  parts.shift()
  return parts.join('\n').trim()
}

export function isInputRequestMessage(message: ChatMessage, executeInputRequest?: { question: string }, executeUserInput?: string) {
  return executeInputRequest && (message.content.includes('需要您的输入') || message.content === '等待用户输入...' || message.content.startsWith('[INPUT_REQUEST]')) && !executeUserInput
}
