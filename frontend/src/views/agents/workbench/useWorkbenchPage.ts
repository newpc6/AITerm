import { onMounted, ref, nextTick, watch } from 'vue'
import { getAgents } from '@/api/aiterm'
import { http } from '@/api/http'
import { getAuthToken } from '@/auth'
import { getApiBaseUrl } from '@/config'
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
  const activeTab = ref('')
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
    return agents.value.find(function (a) {
      return a.id === id
    })
  }

  watch(selectedIds, function (newIds) {
    for (var i = 0; i < newIds.length; i++) {
      var id = newIds[i]
      if (
        !panels.value.find(function (p) {
          return p.agent.id === id
        })
      ) {
        var agent = agentById(id)
        if (agent) {
          var panel = {
            agent: agent,
            messages: [],
            loading: false,
            hasMore: true,
            streaming: false,
            streamDelta: '',
            streamToolCalls: [],
            aborter: null,
            messagesEl: null,
          } as AgentPanel
          panels.value.push(panel)
          loadMessages(panel)
        }
      }
    }
    panels.value = panels.value.filter(function (p) {
      return newIds.includes(p.agent.id)
    })
    if (!activeTab.value || !newIds.includes(activeTab.value)) {
      activeTab.value = newIds.length > 0 ? newIds[0] : ''
    }
  })

  async function loadMessages(panel: AgentPanel, beforeId?: string) {
    panel.loading = true
    try {
      var params: Record<string, string> = { limit: '20' }
      if (beforeId) params.before_id = beforeId
      var resp = await http.get('/api/v1/agents/' + panel.agent.id + '/messages', { params: params })
      var respData = resp.data as ApiResponse<{ messages: AgentMsg[]; has_more: boolean }>
      var newMsgs = (respData.data as { messages: AgentMsg[] }).messages || []
      var hasMore = (respData.data as { has_more: boolean }).has_more
      if (beforeId) {
        panel.messages = newMsgs.concat(panel.messages)
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
    var el = event.target as HTMLElement
    if (el.scrollTop < 50 && panel.hasMore && !panel.loading) {
      var oldest = panel.messages[0]
      if (oldest) loadMessages(panel, oldest.id)
    }
  }

  async function send(panel: AgentPanel) {
    if (!input.value.trim()) return
    sending.value = true
    var msg = input.value.trim()
    input.value = ''
    await sendToAgent(panel, msg)
    sending.value = false
  }

  async function sendToAgent(panel: AgentPanel, message: string) {
    panel.streaming = true
    panel.streamDelta = ''
    panel.streamToolCalls = []
    var aborter = new AbortController()
    panel.aborter = aborter

    panel.messages.push({
      id: '',
      agent_id: panel.agent.id,
      role: 'user',
      content: message,
      tool_calls_json: '[]',
      created_at: new Date().toISOString(),
    })
    await nextTick()
    scrollToBottom(panel)

    var assistantMsg: AgentMsg = {
      id: '',
      agent_id: panel.agent.id,
      role: 'assistant',
      content: '',
      tool_calls_json: '[]',
      created_at: new Date().toISOString(),
    }
    panel.messages.push(assistantMsg)

    try {
      var token = getAuthToken() || ''
      var baseUrl = getApiBaseUrl()
      var url = baseUrl + '/api/v1/agents/' + panel.agent.id + '/chat'
      var headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = 'Bearer ' + token

      var response = await fetch(url, {
        method: 'POST',
        signal: aborter.signal,
        headers: headers,
        body: JSON.stringify({ message: message }),
      })

      if (!response.ok || !response.body) throw new Error('HTTP ' + response.status)

      var reader = response.body.getReader()
      var decoder = new TextDecoder()
      var buffer = ''
      var currentEvent = ''
      var dataLines: string[] = []

      function flushEvent() {
        var d = dataLines.join('\n').trim()
        dataLines = []
        if (!d) {
          currentEvent = ''
          return
        }
        var parsed: any
        try {
          parsed = JSON.parse(d)
        } catch {
          currentEvent = ''
          return
        }

        if (currentEvent === 'delta') {
          var delta = parsed.delta || ''
          assistantMsg.content += delta
          panel.streamDelta = assistantMsg.content
          scrollToBottom(panel)
        } else if (currentEvent === 'reasoning') {
          assistantMsg.content += parsed.delta || ''
        } else if (currentEvent === 'tool_call') {
          panel.streamToolCalls.push({ tool: parsed.tool || '', args: JSON.stringify(parsed.args) })
        } else if (currentEvent === 'done') {
          assistantMsg.content = parsed.reply || assistantMsg.content
          loadMessages(panel)
        } else if (currentEvent === 'error') {
          assistantMsg.content = '错误: ' + (parsed.error || '未知错误')
        }
        currentEvent = ''
      }

      while (true) {
        var result = await reader.read()
        buffer += decoder.decode(result.value || new Uint8Array(), { stream: !result.done })

        var boundaryIndex = buffer.indexOf('\n')
        while (boundaryIndex >= 0) {
          var line = buffer.slice(0, boundaryIndex).replace(/\r$/, '')
          buffer = buffer.slice(boundaryIndex + 1)
          if (!line.trim()) {
            flushEvent()
          } else if (line.indexOf('event:') === 0) {
            currentEvent = line.slice(6).trim()
          } else if (line.indexOf('data:') === 0) {
            dataLines.push(line.slice(5).trim())
          }
          boundaryIndex = buffer.indexOf('\n')
        }

        if (result.done) {
          if (buffer.trim() && buffer.trim().indexOf('data:') === 0) {
            dataLines.push(buffer.trim().slice(5).trim())
          }
          flushEvent()
          break
        }
      }
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
    panel.aborter && panel.aborter.abort()
    panel.streaming = false
  }

  function scrollToBottom(panel: AgentPanel) {
    nextTick(function () {
      var el = msgRefs[panel.agent.id]
      if (el) {
        el.scrollTop = el.scrollHeight
      }
    })
  }

  function setMessagesRef(panel: AgentPanel, el: any) {
    panel.messagesEl = el as HTMLElement | null
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
    var escaped = content.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    escaped = escaped.replace(
      /```(\w*)\n?([\s\S]*?)```/g,
      '<pre style="background:var(--color-bg-input);padding:8px;border-radius:6px;overflow:auto;font-size:12px;line-height:1.4"><code>$2</code></pre>',
    )
    escaped = escaped.replace(/`([^`]+)`/g, '<code style="background:var(--color-bg-input);padding:1px 4px;border-radius:3px;font-size:12px">$1</code>')
    escaped = escaped.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    escaped = escaped.replace(/\*([^*]+)\*/g, '<em>$1</em>')
    escaped = escaped.replace(/\n/g, '<br>')
    return escaped
  }

  function parseToolCalls(json: string): { name: string; arguments: string }[] {
    try {
      return JSON.parse(json)
    } catch {
      return []
    }
  }

  function agentLabel(agent: AgentItem): string {
    return agent.name + ' (' + (agent.model_name || '无模型') + ')'
  }

  function getPanel(agentId: string): AgentPanel | undefined {
    return panels.value.find(function (p) {
      return p.agent.id === agentId
    })
  }

  const msgRefs: Record<string, HTMLElement | null> = {}

  function getRef(id: string) {
    return function (el: any) {
      msgRefs[id] = el
    }
  }

  function closeTab(id: string) {
    selectedIds.value = selectedIds.value.filter(function (sid) {
      return sid !== id
    })
  }

  onMounted(function () {
    loadAgents()
  })

  return {
    agents,
    selectedIds,
    panels,
    activeTab,
    input,
    sending,
    send,
    stopPanel,
    onPanelScroll,
    setMessagesRef,
    formatTime,
    renderContent,
    parseToolCalls,
    agentLabel,
    getPanel,
    getRef,
    closeTab,
    loadMessages,
  }
}
