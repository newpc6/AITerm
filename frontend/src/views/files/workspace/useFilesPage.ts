import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { http } from '@/api/http'
import type { ApiResponse } from '@/types/api'

interface FileNode {
  name: string
  path: string
  is_dir: boolean
  size: number
  modified: string
  children?: FileNode[]
}

export function useFilesPage() {
  const loading = ref(false)
  const rootNodes = ref<FileNode[]>([])
  const expandedDirs = ref<Set<string>>(new Set())
  const selectedNode = ref<FileNode | null>(null)
  const fileContent = ref('')
  const fileLoading = ref(false)
  const saving = ref(false)
  const creating = ref<string | null>(null)
  const newName = ref('')
  const renaming = ref<string | null>(null)
  const renameValue = ref('')

  async function loadTree() {
    loading.value = true
    try {
      const { data } = await http.get<ApiResponse<FileNode[]>>('/api/v1/workspace/files')
      rootNodes.value = (data.data || []) as FileNode[]
    } catch {
      rootNodes.value = []
    } finally {
      loading.value = false
    }
  }

  function toggleDir(node: FileNode) {
    if (expandedDirs.value.has(node.path)) {
      expandedDirs.value.delete(node.path)
    } else {
      expandedDirs.value.add(node.path)
    }
    expandedDirs.value = new Set(expandedDirs.value)
  }

  async function selectNode(node: FileNode) {
    selectedNode.value = node
    if (node.is_dir) {
      toggleDir(node)
      fileContent.value = ''
      return
    }
    fileLoading.value = true
    try {
      const { data } = await http.get<ApiResponse<{ content: string }>>('/api/v1/workspace/files/read', { params: { path: node.path } })
      fileContent.value = (data.data as { content: string })?.content || ''
    } catch {
      fileContent.value = ''
    } finally {
      fileLoading.value = false
    }
  }

  async function saveFile() {
    if (!selectedNode.value || selectedNode.value.is_dir) return
    saving.value = true
    try {
      await http.post('/api/v1/workspace/files/write', { path: selectedNode.value.path, content: fileContent.value })
      ElMessage.success('已保存')
    } catch {
      ElMessage.error('保存失败')
    } finally {
      saving.value = false
    }
  }

  function startCreate(parentPath: string) {
    creating.value = parentPath
    newName.value = ''
  }

  async function confirmCreate(isDir: boolean) {
    const parentPath = creating.value || ''
    if (!newName.value.trim()) {
      creating.value = null
      return
    }
    const fullPath = parentPath ? `${parentPath}/${newName.value.trim()}` : `/${newName.value.trim()}`
    try {
      if (isDir) {
        await http.post('/api/v1/workspace/files/mkdir', { path: fullPath })
      } else {
        await http.post('/api/v1/workspace/files/write', { path: fullPath, content: '' })
      }
      ElMessage.success('已创建')
      creating.value = null
      newName.value = ''
      expandedDirs.value.add(parentPath)
      expandedDirs.value = new Set(expandedDirs.value)
      await loadTree()
    } catch {
      ElMessage.error('创建失败')
    }
  }

  function startRename(node: FileNode) {
    renaming.value = node.path
    renameValue.value = node.name
  }

  async function confirmRename() {
    const oldPath = renaming.value
    if (!oldPath || !renameValue.value.trim()) {
      renaming.value = null
      return
    }
    const parts = oldPath.split('/')
    parts.pop()
    const newPath = parts.join('/') + '/' + renameValue.value.trim()
    try {
      await http.post('/api/v1/workspace/files/rename', { old_path: oldPath, new_path: newPath })
      ElMessage.success('已重命名')
      renaming.value = null
      if (selectedNode.value?.path === oldPath) {
        selectedNode.value.path = newPath
      }
      await loadTree()
    } catch {
      ElMessage.error('重命名失败')
    }
  }

  async function deleteNode(node: FileNode) {
    try {
      const label = node.is_dir ? `删除目录 "${node.name}" 及其所有内容？` : `删除文件 "${node.name}"？`
      await ElMessageBox.confirm(label, '删除确认', { type: 'warning' })
      await http.post('/api/v1/workspace/files/delete', { path: node.path })
      ElMessage.success('已删除')
      if (selectedNode.value?.path === node.path) {
        selectedNode.value = null
        fileContent.value = ''
      }
      await loadTree()
    } catch {
      /* */
    }
  }

  function flattenNodes(nodes: FileNode[], parentExpanded: boolean): { node: FileNode; depth: number }[] {
    const result: { node: FileNode; depth: number }[] = []
    for (const n of nodes) {
      result.push({ node: n, depth: 0 })
      if (expandedDirs.value.has(n.path) && n.children) {
        for (const c of flattenChildren(n.children, 1)) {
          result.push(c)
        }
      }
    }
    return result
  }

  function flattenChildren(nodes: FileNode[], depth: number): { node: FileNode; depth: number }[] {
    const result: { node: FileNode; depth: number }[] = []
    for (const n of nodes) {
      result.push({ node: n, depth })
      if (expandedDirs.value.has(n.path) && n.children) {
        for (const c of flattenChildren(n.children, depth + 1)) {
          result.push(c)
        }
      }
    }
    return result
  }

  const flatNodes = ref<{ node: FileNode; depth: number }[]>([])

  function recomputeFlat() {
    flatNodes.value = flattenNodes(rootNodes.value, false)
  }

  function onContextMenu(event: MouseEvent, node: FileNode) {
    event.preventDefault()
    event.stopPropagation()
    const items = [
      ...(node.is_dir
        ? [
            { label: '新建文件', action: () => startCreate(node.path) },
            { label: '新建文件夹', action: () => startCreate(node.path) },
          ]
        : []),
      { label: '重命名', action: () => startRename(node) },
      { label: '删除', action: () => deleteNode(node), divided: true },
    ]
    const menu = document.createElement('div')
    menu.className = 'tagsview-context-menu'
    menu.style.cssText = `position:fixed;left:${event.clientX}px;top:${event.clientY}px;z-index:9999;background:var(--color-bg-card);border:1px solid var(--color-border-primary);border-radius:8px;padding:4px 0;min-width:140px;box-shadow:0 4px 16px rgba(0,0,0,0.3);`
    const closeMenu = () => {
      menu.remove()
      document.removeEventListener('click', closeMenu)
    }
    items.forEach((item) => {
      const el = document.createElement('div')
      el.textContent = item.label
      el.style.cssText = `padding:6px 16px;font-size:13px;cursor:pointer;color:var(--color-text-secondary);${(item as { divided?: boolean }).divided ? 'border-top:1px solid var(--color-border-primary);margin-top:4px;padding-top:10px;' : ''}`
      el.onmouseenter = () => {
        el.style.background = 'var(--color-bg-card-hover)'
      }
      el.onmouseleave = () => {
        el.style.background = 'transparent'
      }
      el.onclick = () => {
        item.action()
        closeMenu()
      }
      menu.appendChild(el)
    })
    document.body.appendChild(menu)
    setTimeout(() => document.addEventListener('click', closeMenu), 0)
  }

  function handleRootContextMenu(event: MouseEvent) {
    event.preventDefault()
    const items = [
      { label: '新建文件', action: () => startCreate('') },
      { label: '新建文件夹', action: () => startCreate('') },
    ]
    const menu = document.createElement('div')
    menu.className = 'tagsview-context-menu'
    menu.style.cssText = `position:fixed;left:${event.clientX}px;top:${event.clientY}px;z-index:9999;background:var(--color-bg-card);border:1px solid var(--color-border-primary);border-radius:8px;padding:4px 0;min-width:140px;box-shadow:0 4px 16px rgba(0,0,0,0.3);`
    const closeMenu = () => {
      menu.remove()
      document.removeEventListener('click', closeMenu)
    }
    items.forEach((item) => {
      const el = document.createElement('div')
      el.textContent = item.label
      el.style.cssText = 'padding:6px 16px;font-size:13px;cursor:pointer;color:var(--color-text-secondary);'
      el.onmouseenter = () => {
        el.style.background = 'var(--color-bg-card-hover)'
      }
      el.onmouseleave = () => {
        el.style.background = 'transparent'
      }
      el.onclick = () => {
        item.action()
        closeMenu()
      }
      menu.appendChild(el)
    })
    document.body.appendChild(menu)
    setTimeout(() => document.addEventListener('click', closeMenu), 0)
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  onMounted(async () => {
    await loadTree()
    recomputeFlat()
  })

  return {
    loading,
    flatNodes,
    recomputeFlat,
    selectedNode,
    fileContent,
    fileLoading,
    saving,
    creating,
    newName,
    confirmCreate,
    renaming,
    renameValue,
    startRename,
    confirmRename,
    toggleDir,
    selectNode,
    saveFile,
    startCreate,
    deleteNode,
    onContextMenu,
    handleRootContextMenu,
    formatSize,
    loadTree,
    expandedDirs,
  }
}
