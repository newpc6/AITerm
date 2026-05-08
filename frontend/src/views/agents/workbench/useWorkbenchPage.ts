import { onMounted, ref } from 'vue'
import { getAgents } from '@/api/aiterm'
import type { AgentItem } from '@/types/api'

const STORAGE_KEY = 'aiterm:workbench:selected'

function loadPersisted(): string[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as string[]) : []
  } catch {
    return []
  }
}

function persistSelected(ids: string[]) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(ids))
}

export function useWorkbenchPage() {
  const agents = ref<AgentItem[]>([])
  const selectedIds = ref<string[]>([])
  const activeId = ref('')

  const displaySettings = ref({
    showThinking: true,
    expandThinking: false,
    showTools: true,
    expandTools: false,
    showFullInput: true,
    expandFullInput: false,
    autoCollapse: true,
  })

  async function loadAgents() {
    try {
      agents.value = await getAgents()
      const persisted = loadPersisted()
      if (persisted.length > 0) {
        selectedIds.value = persisted.filter(function (id) {
          return agents.value.some(function (a) {
            return a.id === id
          })
        })
        if (selectedIds.value.length > 0) {
          activeId.value = selectedIds.value[0]
          return
        }
      }
      if (agents.value.length > 0) {
        const def = agents.value.find(function (a) {
          return a.is_default
        })
        const firstId = def ? def.id : agents.value[0].id
        selectedIds.value = [firstId]
        activeId.value = firstId
        persistSelected(selectedIds.value)
      }
    } catch {
      agents.value = []
    }
  }

  function selectAgent(id: string) {
    if (!selectedIds.value.includes(id)) {
      selectedIds.value = [...selectedIds.value, id]
      persistSelected(selectedIds.value)
    }
    activeId.value = id
  }

  function removeAgent(id: string) {
    selectedIds.value = selectedIds.value.filter(function (s) {
      return s !== id
    })
    persistSelected(selectedIds.value)
    if (activeId.value === id) {
      activeId.value = selectedIds.value.length > 0 ? selectedIds.value[0] : ''
    }
  }

  function getAgentName(id: string) {
    const a = agents.value.find(function (x) {
      return x.id === id
    })
    return a ? a.name : id
  }

  const sidebarCollapsed = ref(false)

  onMounted(function () {
    loadAgents()
  })

  return { agents, selectedIds, activeId, displaySettings, sidebarCollapsed, selectAgent, removeAgent, getAgentName }
}
