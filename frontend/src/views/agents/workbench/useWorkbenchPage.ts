import { onMounted, ref } from 'vue'
import { getAgents } from '@/api/aiterm'
import type { AgentItem } from '@/types/api'

export function useWorkbenchPage() {
  const agents = ref<AgentItem[]>([])
  const selectedIds = ref<string[]>([])
  const activeTab = ref('')

  const displaySettings = ref({
    showThinking: true,
    expandThinking: false,
    showTools: true,
    expandTools: false,
    showInput: true,
    expandInput: false,
    showFullInput: false,
    expandFullInput: false,
    autoCollapse: true,
  })

  const showShareDialog = ref(false)

  async function loadAgents() {
    try {
      agents.value = await getAgents()
      if (agents.value.length > 0 && selectedIds.value.length === 0) {
        var def = agents.value.find(function (a) {
          return a.is_default
        })
        var firstId = def ? def.id : agents.value[0].id
        selectedIds.value = [firstId]
        activeTab.value = firstId
      }
    } catch {
      agents.value = []
    }
  }

  function onSelectChange(ids: string[]) {
    selectedIds.value = ids
    if (activeTab.value && !ids.includes(activeTab.value)) {
      activeTab.value = ids.length > 0 ? ids[0] : ''
    }
    if (!activeTab.value && ids.length > 0) {
      activeTab.value = ids[0]
    }
  }

  function getAgentName(id: string) {
    var a = agents.value.find(function (x) {
      return x.id === id
    })
    return a ? a.name : id
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

  return { agents, selectedIds, activeTab, displaySettings, showShareDialog, onSelectChange, getAgentName, closeTab }
}
