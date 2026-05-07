import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { http } from '@/api/http'
import type { ApiResponse } from '@/types/api'

interface FileItem { name: string; path: string; is_dir: boolean; size: number; modified: string }

export function useFilesPage() {
  const loading = ref(false)
  const currentPath = ref('')
  const items = ref<FileItem[]>([])
  const fileContent = ref('')
  const editingFile = ref('')
  const saving = ref(false)
  const newItemName = ref('')
  const creating = ref(false)

  async function loadDir(path?: string) {
    loading.value = true
    try {
      const { data } = await http.get<ApiResponse<FileItem[]>>('/api/v1/workspace/files', { params: { path: path || currentPath.value || '/' } })
      items.value = data.data || []
    } catch { ElMessage.error('加载目录失败') }
    finally { loading.value = false }
  }

  function navigate(item: FileItem) {
    if (item.is_dir) { currentPath.value = item.path; loadDir(item.path) }
    else { loadFile(item.path) }
  }

  function goUp() {
    const parts = currentPath.value.replace(/\\/g, '/').split('/').filter(Boolean)
    parts.pop()
    currentPath.value = '/' + parts.join('/')
    loadDir()
  }

  async function loadFile(path: string) {
    try {
      const { data } = await http.get<ApiResponse<{ content: string }>>('/api/v1/workspace/files/read', { params: { path } })
      fileContent.value = (data.data as { content: string })?.content || ''
      editingFile.value = path
    } catch { ElMessage.error('读取文件失败') }
  }

  async function saveFile() {
    saving.value = true
    try {
      await http.post('/api/v1/workspace/files/write', { path: editingFile.value, content: fileContent.value })
      ElMessage.success('已保存')
    } catch { ElMessage.error('保存失败') }
    finally { saving.value = false }
  }

  function closeEditor() { editingFile.value = ''; fileContent.value = '' }

  async function createDir() {
    if (!newItemName.value.trim()) return
    creating.value = true
    try {
      await http.post('/api/v1/workspace/files/mkdir', { path: `${currentPath.value}/${newItemName.value}` })
      ElMessage.success('已创建'); newItemName.value = ''; await loadDir()
    } catch { ElMessage.error('创建失败') }
    finally { creating.value = false }
  }

  async function createFile() {
    if (!newItemName.value.trim()) return
    creating.value = true
    try {
      await http.post('/api/v1/workspace/files/write', { path: `${currentPath.value}/${newItemName.value}`, content: '' })
      ElMessage.success('已创建'); newItemName.value = ''; await loadDir()
    } catch { ElMessage.error('创建失败') }
    finally { creating.value = false }
  }

  async function deleteItem(path: string) {
    try {
      await ElMessageBox.confirm(`确定删除 ${path} 吗？`, '删除确认', { type: 'warning' })
      await http.post('/api/v1/workspace/files/delete', { path })
      ElMessage.success('已删除'); await loadDir()
    } catch { /* */ }
  }

  onMounted(() => { loadDir() })

  return { loading, currentPath, items, fileContent, editingFile, saving, newItemName, creating, loadDir, navigate, goUp, saveFile, closeEditor, createDir, createFile, deleteItem }
}
