import { onMounted, ref } from 'vue'
import { getAgents, runAgentWorkbench } from '@/api/aiterm'
import type { AgentItem } from '@/types/api'

interface AgentRun {
  agentId: string
  agentName: string
  modelName: string
  status: 'idle' | 'running' | 'done' | 'error'
  delta: string
  toolCalls: { tool: string; args: Record<string, unknown>; output?: string }[]
  reply: string
  error: string
  duration: number
  aborted: boolean
}

export function useWorkbenchPage() {
  const agents = ref<AgentItem[]>([])
  const loading = ref(false)
  const message = ref('')
  const running = ref(false)
  const selectedAgentIds = ref<string[]>([])
  const runs = ref<AgentRun[]>([])
  let abortController: AbortController | null = null

  async function load() {
    loading.value = true
    try { agents.value = await getAgents() } catch { agents.value = [] }
    finally { loading.value = false }
  }

  function toggleAgent(id: string) {
    const idx = selectedAgentIds.value.indexOf(id)
    if (idx >= 0) selectedAgentIds.value.splice(idx, 1)
    else selectedAgentIds.value.push(id)
  }

  function selectAll() {
    if (selectedAgentIds.value.length === agents.value.length) {
      selectedAgentIds.value = []
    } else {
      selectedAgentIds.value = agents.value.map(a => a.id)
    }
  }

  async function start() {
    if (!message.value.trim() || selectedAgentIds.value.length === 0) return
    running.value = true
    abortController = new AbortController()

    runs.value = selectedAgentIds.value.map(aid => ({
      agentId: aid,
      agentName: agents.value.find(a => a.id === aid)?.name || aid,
      modelName: agents.value.find(a => a.id === aid)?.model_name || '',
      status: 'idle' as const,
      delta: '', toolCalls: [], reply: '', error: '', duration: 0, aborted: false,
    }))

    try {
      await runAgentWorkbench(
        { agent_ids: selectedAgentIds.value, message: message.value },
        (event, data) => {
          const aid = data.agent_id as string
          const run = runs.value.find(r => r.agentId === aid)
          if (!run) return

          if (event === 'agent.start') {
            run.status = 'running'
          } else if (event === 'agent.delta') {
            run.delta += (data.delta as string) || ''
          } else if (event === 'agent.tool_call') {
            run.toolCalls.push({ tool: (data.tool as string) || '', args: (data.args as Record<string, unknown>) || {} })
          } else if (event === 'agent.done') {
            run.reply = (data.reply as string) || ''
            run.status = 'done'
          } else if (event === 'agent.error') {
            run.error = (data.error as string) || ''
            run.status = 'error'
          }
        },
        abortController.signal,
      )
    } catch (e) {
      if ((e as Error).name !== 'AbortError') {
        runs.value.forEach(r => { if (r.status === 'idle') { r.status = 'error'; r.error = String(e) } })
      }
    } finally {
      running.value = false
    }
  }

  function stop() {
    abortController?.abort()
    running.value = false
  }

  onMounted(() => { void load() })

  return {
    agents, loading, message, running, selectedAgentIds, runs,
    toggleAgent, selectAll, start, stop,
  }
}
