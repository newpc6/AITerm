import { computed, nextTick, onMounted, ref } from 'vue'

import { executeTerminalCommand, getNodes } from '@/api/aiterm'
import { getAllCommands, type CommandItem, type PlatformCommands } from './commands'
import { formatDateTime } from '@/utils/datetime'
import type { NodeItem, TerminalExecuteData } from '@/types/api'

type HistoryEntry = {
  id: string
  command: string
  output: string
  exitCode: number
  timestamp: string
  nodeId: string
  nodeName: string
}

export function useTerminalPage() {
  const loading = ref(false)
  const errorMessage = ref('')
  const nodes = ref<NodeItem[]>([])
  const selectedNodeId = ref('')
  const commandInput = ref('')
  const history = ref<HistoryEntry[]>([])
  const terminalRef = ref<HTMLElement | null>(null)
  const showCommandPanel = ref(true)
  const selectedPlatform = ref<'common' | 'windows' | 'linux' | 'mac'>('common')

  const allCommands = getAllCommands()

  async function loadNodes() {
    try {
      const data = await getNodes()
      nodes.value = data.items

      if (!selectedNodeId.value && data.items.length > 0) {
        selectedNodeId.value = data.items[0].id
      }
    } catch {
      errorMessage.value = '节点列表接口不可用。'
    }
  }

  async function executeCommand() {
    const command = commandInput.value.trim()
    if (!command || loading.value) {
      return
    }

    loading.value = true
    errorMessage.value = ''

    try {
      const result: TerminalExecuteData = await executeTerminalCommand({
        command,
        node_id: selectedNodeId.value || undefined,
      })

      history.value.push({
        id: `cmd-${Date.now()}`,
        command: result.command,
        output: result.output,
        exitCode: result.exit_code,
        timestamp: result.timestamp,
        nodeId: result.node_id,
        nodeName: result.node_name,
      })

      commandInput.value = ''

      await nextTick()
      scrollToBottom()
    } catch {
      errorMessage.value = '命令执行失败。'
    } finally {
      loading.value = false
    }
  }

  function scrollToBottom() {
    if (terminalRef.value) {
      terminalRef.value.scrollTop = terminalRef.value.scrollHeight
    }
  }

  function clearHistory() {
    history.value = []
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void executeCommand()
    }
  }

  function insertCommand(command: string) {
    commandInput.value = command
  }

  function toggleCommandPanel() {
    showCommandPanel.value = !showCommandPanel.value
  }

  onMounted(() => {
    void loadNodes()
  })

  const selectedNode = computed(() => nodes.value.find((n) => n.id === selectedNodeId.value))

  const currentCommands = computed(() => {
    if (selectedPlatform.value === 'common') {
      return {
        name: allCommands.common.name,
        categories: [allCommands.common],
      } as PlatformCommands
    }
    return allCommands[selectedPlatform.value]
  })

  return {
    allCommands,
    clearHistory,
    commandInput,
    currentCommands,
    errorMessage,
    executeCommand,
    formatDateTime,
    handleKeydown,
    history,
    insertCommand,
    loading,
    nodes,
    selectedNode,
    selectedNodeId,
    selectedPlatform,
    showCommandPanel,
    terminalRef,
    toggleCommandPanel,
  }
}
