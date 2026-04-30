import { computed, onMounted, ref } from 'vue'
import { ElMessageBox } from 'element-plus'

import { createNode, deleteNode, getHealth, getNodes, updateNode } from '@/api/aiterm'
import type { NodeItem, NodePayload } from '@/types/api'

function createDefaultForm(): NodePayload {
  return {
    name: '',
    host: '',
    port: 22,
  }
}

export function useNodesPage() {
  const loading = ref(false)
  const saving = ref(false)
  const status = ref('unknown')
  const errorMessage = ref('')
  const successMessage = ref('')
  const nodes = ref<NodeItem[]>([])
  const form = ref<NodePayload>(createDefaultForm())
  const editingNode = ref<NodeItem | null>(null)
  const dialogVisible = ref(false)
  const page = ref(1)
  const pageSize = ref(10)
  const total = ref(0)

  async function loadNodes() {
    loading.value = true
    errorMessage.value = ''

    try {
      const [health, data] = await Promise.all([getHealth(), getNodes({ page: page.value, page_size: pageSize.value })])
      status.value = health.status
      nodes.value = data.items
      total.value = data.total
    } catch {
      status.value = 'offline'
      errorMessage.value = '节点接口不可用。'
    } finally {
      loading.value = false
    }
  }

  function handlePageChange(newPage: number) {
    page.value = newPage
    void loadNodes()
  }

  function handlePageSizeChange(newSize: number) {
    pageSize.value = newSize
    page.value = 1
    void loadNodes()
  }

  function syncFormFromNode(node: NodeItem) {
    form.value = {
      name: node.name,
      host: node.host,
      port: node.port,
    }
  }

  function startCreateNode() {
    editingNode.value = null
    form.value = createDefaultForm()
    successMessage.value = ''
    errorMessage.value = ''
    dialogVisible.value = true
  }

  function startEditNode(node: NodeItem) {
    editingNode.value = node
    syncFormFromNode(node)
    successMessage.value = ''
    errorMessage.value = ''
    dialogVisible.value = true
  }

  function closeDialog() {
    dialogVisible.value = false
    editingNode.value = null
    form.value = createDefaultForm()
    successMessage.value = ''
    errorMessage.value = ''
  }

  async function saveNode() {
    saving.value = true
    errorMessage.value = ''
    successMessage.value = ''

    try {
      if (editingNode.value) {
        await updateNode(editingNode.value.id, form.value)
        successMessage.value = '节点更新成功。'
      } else {
        await createNode(form.value)
        successMessage.value = '节点创建成功。'
      }
      closeDialog()
      await loadNodes()
    } catch {
      errorMessage.value = editingNode.value ? '更新节点失败。' : '创建节点失败。'
    } finally {
      saving.value = false
    }
  }

  async function removeNode(node: NodeItem) {
    errorMessage.value = ''
    successMessage.value = ''

    try {
      await ElMessageBox.confirm(`确定删除节点 ${node.name} 吗？`, '删除节点', {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
      })
    } catch {
      return
    }

    loading.value = true
    try {
      await deleteNode(node.id)
      successMessage.value = '节点删除成功。'
      total.value = Math.max(0, total.value - 1)
      if (nodes.value.length === 0 && page.value > 1) {
        page.value -= 1
      }
      await loadNodes()
    } catch {
      errorMessage.value = '删除节点失败。'
    } finally {
      loading.value = false
    }
  }

  const nodeCount = computed(() => total.value)
  const isEditing = computed(() => !!editingNode.value)
  const dialogTitle = computed(() => (editingNode.value ? '编辑节点' : '添加节点'))

  onMounted(() => {
    void loadNodes()
  })

  return {
    closeDialog,
    dialogTitle,
    dialogVisible,
    editingNode,
    errorMessage,
    form,
    isEditing,
    loading,
    loadNodes,
    nodeCount,
    nodes,
    removeNode,
    saving,
    startCreateNode,
    startEditNode,
    saveNode,
    status,
    successMessage,
    page,
    pageSize,
    total,
    handlePageChange,
    handlePageSizeChange,
  }
}
