import { onMounted, ref, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getAgents, runAgentWorkbench } from '@/api/aiterm'
import { http } from '@/api/http'
import type { ApiResponse, AgentItem } from '@/types/api'

interface AgentMsg {
  id: string
  agent_id: string
  role: string
  content: string
  tool_calls_json: string
  created_at: string
}

interface AgentPanel {
  agent: AgentItem
  messages: AgentMsg[]
  loading: boolean
  hasMore: boolean
  streaming: boolean
  streamDelta: string
  streamToolCalls: { tool: string; args: string }[]
  aborter: AbortController | null
  messagesEl: HTMLElement | null
}

export function useWorkbenchPage() {
  const agents = ref<AgentItem[]>([])
  const selectedIds = ref<string[]>([])
  const panels = ref<AgentPanel[]>([])
  const input = ref('')
  const sending = ref(false)

  async function loadAgents() {
    try {
      agents.value = await getAgents()
    } catch {
      agents.value = []
    }
  }

  function agentById(id: string) {
    return agents.value.find((a) => a.id === id)
  }

  watch(selectedIds, (newIds) => {
    for (const id of newIds) {
      if (!panels.value.find((p) => p.agent.id === id)) {
        const agent = agentById(id)
        if (agent) {
          const panel: AgentPanel = {
            agent,
            messages: [],
            loading: false,
            hasMore: true,
            streaming: false,
            streamDelta: '',
            streamToolCalls: [],
            aborter: null,
            messagesEl: null,
          }
          panels.value.push(panel)
          loadMessages(panel)
        }
      }
    }
    panels.value = panels.value.filter((p) => newIds.includes(p.agent.id))
  })

  async function loadMessages(panel: AgentPanel, beforeId?: string) {
    panel.loading = true
    try {
      const { data } = await http.get<ApiResponse<{ messages: AgentMsg[]; has_more: boolean }>>(`/api/v1/agents/${panel.agent.id}/messages`, { params: { before_id: beforeId || '', limit: 20 } })
      const newMsgs = (data.data as { messages: AgentMsg[] }).messages || []
      const hasMore = (data.data as { has_more: boolean }).has_more

      if (beforeId) {
        panel.messages = [...newMsgs, ...panel.messages]
      } else {
        panel.messages = newMsgs
      }
      panel.hasMore = hasMore
    } catch {
      /* */
    } finally {
      panel.loading = false
    }
  }

  function onPanelScroll(panel: AgentPanel, event: Event) {
    const el = event.target as HTMLElement
    if (el.scrollTop < 50 && panel.hasMore && !panel.loading) {
      const oldest = panel.messages[0]
      if (oldest) loadMessages(panel, oldest.id)
    }
  }

  async function send() {
    if (!input.value.trim() || selectedIds.value.length === 0) return
    sending.value = true
    const msg = input.value.trim()
    input.value = ''

    const activePanels = panels.value.filter((p) => selectedIds.value.includes(p.agent.id))
    const promises = activePanels.map((panel) => sendToAgent(panel, msg))
    await Promise.allSettled(promises)
    sending.value = false
  }

  async function sendToAgent(panel: AgentPanel, message: string) {
    panel.streaming = true
    panel.streamDelta = ''
    panel.streamToolCalls = []
    const aborter = new AbortController()
    panel.aborter = aborter

    panel.messages.push({ id: '', agent_id: panel.agent.id, role: 'user', content: message, tool_calls_json: '[]', created_at: new Date().toISOString() })
    await nextTick()
    scrollToBottom(panel)

    const assistantMsg: AgentMsg = { id: '', agent_id: panel.agent.id, role: 'assistant', content: '', tool_calls_json: '[]', created_at: new Date().toISOString() }
    panel.messages.push(assistantMsg)

    try {
      await runAgentWorkbench(
        { agent_ids: [panel.agent.id], message },
        (event, data) => {
          if (event === 'agent.delta') {
            assistantMsg.content += (data.delta as string) || ''
            panel.streamDelta = assistantMsg.content
            scrollToBottom(panel)
          } else if (event === 'agent.reasoning') {
            assistantMsg.content += (data.delta as string) || ''
          } else if (event === 'agent.tool_call') {
            panel.streamToolCalls.push({ tool: (data.tool as string) || '', args: JSON.stringify(data.args) })
          } else if (event === 'agent.done') {
            assistantMsg.content = (data.reply as string) || assistantMsg.content
            if (data.reply) assistantMsg.content = data.reply as string
            loadMessages(panel) // reload from server
          } else if (event === 'agent.error') {
            assistantMsg.content = '错误: ' + ((data.error as string) || '未知错误')
          }
        },
        aborter.signal,
      )
    } catch (e) {
      if ((e as Error).name !== 'AbortError') {
        assistantMsg.content = '请求失败: ' + String(e)
      }
    }
    panel.streaming = false
    panel.streamDelta = ''
    panel.streamToolCalls = []
    panel.aborter = null
    scrollToBottom(panel)
  }

  function stopPanel(panel: AgentPanel) {
    panel.aborter?.abort()
    panel.streaming = false
  }

  function scrollToBottom(panel: AgentPanel) {
    nextTick(() => {
      if (panel.messagesEl) {
        panel.messagesEl.scrollTop = panel.messagesEl.scrollHeight
      }
    })
  }

  function setMessagesRef(panel: AgentPanel, el: HTMLElement) {
    panel.messagesEl = el
  }

  function formatTime(ts: string) {
    if (!ts) return ''
    try {
      return new Date(ts).toLocaleTimeString()
    } catch {
      return ''
    }
  }

  function renderContent(content: string) {
    if (!content) return ''
    return content
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre style="background:var(--color-bg-input);padding:8px;border-radius:6px;overflow:auto;font-size:12px;line-height:1.4"><code>$2</code></pre>')
      .replace(/`([^`]+)`/g, '<code style="background:var(--color-bg-input);padding:1px 4px;border-radius:3px;font-size:12px">$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\*([^*]+)\*/g, '<em>$1</em>')
      .replace(/\n/g, '<br>')
  }

  function parseToolCalls(json: string): { name: string; arguments: string }[] {
    try {
      return JSON.parse(json)
    } catch {
      return []
    }
  }

  onMounted(() => {
    void loadAgents()
  })

  return {
    agents,
    selectedIds,
    panels,
    input,
    sending,
    send,
    stopPanel,
    onPanelScroll,
    setMessagesRef,
    formatTime,
    renderContent,
    parseToolCalls,
  }
}
