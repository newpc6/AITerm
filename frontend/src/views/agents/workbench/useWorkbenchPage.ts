import { onMounted, ref } from 'vue'
import { getAgents } from '@/api/aiterm'
import type { AgentItem } from '@/types/api'

export function useWorkbenchPage() {
  const agents = ref<AgentItem[]>([])
  const selectedIds = ref<string[]>([])
  const activeTab = ref('')

  async function loadAgents() {
    try {
      agents.value = await getAgents()
      if (agents.value.length > 0) {
        const def = agents.value.find(function (a) {
          return a.is_default
        })
        const firstId = def ? def.id : agents.value[0].id
        if (selectedIds.value.length === 0) {
          selectedIds.value = [firstId]
          activeTab.value = firstId
        }
      }
    } catch {
      agents.value = []
    }
  }

  function agentById(id: string) {
    return agents.value.find(function (a) {
      return a.id === id
    })
  }

  function getAgentName(id: string) {
    const a = agentById(id)
    return a ? a.name : id
  }

  function selectAgent(id: string) {
    if (!selectedIds.value.includes(id)) {
      selectedIds.value = [...selectedIds.value, id]
    }
    activeTab.value = id
  }

  function closeTab(id: string) {
    selectedIds.value = selectedIds.value.filter(function (s) {
      return s !== id
    })
    if (activeTab.value === id) {
      activeTab.value = selectedIds.value.length > 0 ? selectedIds.value[0] : ''
    }
  }

  onMounted(function () {
    loadAgents()
  })

  return {
    agents,
    selectedIds,
    activeTab,
    getAgentName,
    selectAgent,
    closeTab,
  }
}
