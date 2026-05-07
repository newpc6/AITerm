import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getSandboxConfig, updateSandboxConfig,
  addSandboxPath, deleteSandboxPath,
  addDangerousPattern, updateDangerousPattern, deleteDangerousPattern,
  addBlacklistItem, updateBlacklistItem, deleteBlacklistItem,
  addWhitelistItem, updateWhitelistItem, deleteWhitelistItem,
} from '@/api/aiterm'
import type {
  SandboxFullConfig, SandboxConfigUpdate,
  SandboxPath, SandboxDangerousPattern, SandboxCommandItem,
} from '@/types/api'

export function useSandboxPage() {
  const loading = ref(false)
  const saving = ref(false)

  const config = ref<SandboxFullConfig | null>(null)
  const form = ref<SandboxConfigUpdate>({})
  const paths = ref<SandboxPath[]>([])
  const dangerousPatterns = ref<SandboxDangerousPattern[]>([])
  const blacklist = ref<SandboxCommandItem[]>([])
  const whitelist = ref<SandboxCommandItem[]>([])

  const showPathDialog = ref(false)
  const newPath = ref('')

  const showPatternDialog = ref(false)
  const editingPatternId = ref<string | null>(null)
  const patternForm = ref({ pattern: '', description: '', scope: 'server' })

  const showBlacklistDialog = ref(false)
  const editingBlacklistId = ref<string | null>(null)
  const blacklistForm = ref({ command: '', scope: 'server' })

  const showWhitelistDialog = ref(false)
  const editingWhitelistId = ref<string | null>(null)
  const whitelistForm = ref({ command: '', scope: 'server' })

  function syncForm(data: SandboxFullConfig) {
    form.value = {
      mode: data.config.mode,
      rules_prompt: data.config.rules_prompt,
      require_confirm: data.config.require_confirm,
      max_file_size_mb: data.config.max_file_size_mb,
      docker_image: data.config.docker_image,
      docker_network: data.config.docker_network,
      docker_memory: data.config.docker_memory,
      docker_cpu: data.config.docker_cpu,
      docker_timeout: data.config.docker_timeout,
      docker_auto_remove: data.config.docker_auto_remove,
    }
    paths.value = data.paths
    dangerousPatterns.value = data.dangerous_patterns
    blacklist.value = data.command_blacklist
    whitelist.value = data.command_whitelist
  }

  async function loadConfig() {
    loading.value = true
    try {
      config.value = await getSandboxConfig()
      syncForm(config.value)
    } catch {
      ElMessage.error('加载沙盒配置失败')
    } finally {
      loading.value = false
    }
  }

  async function saveSettings() {
    saving.value = true
    try {
      await updateSandboxConfig(form.value)
      ElMessage.success('配置已保存')
    } catch {
      ElMessage.error('保存配置失败')
    } finally {
      saving.value = false
    }
  }

  function resetForm() {
    if (!config.value) return
    syncForm(config.value)
  }

  async function handleAddPath() {
    const val = newPath.value.trim()
    if (!val) return
    try {
      const item = await addSandboxPath(val)
      paths.value.push(item)
      newPath.value = ''
      showPathDialog.value = false
      ElMessage.success('路径已添加')
    } catch {
      ElMessage.error('添加失败')
    }
  }

  async function handleDeletePath(id: string) {
    try {
      await deleteSandboxPath(id)
      paths.value = paths.value.filter(p => p.id !== id)
      ElMessage.success('路径已删除')
    } catch {
      ElMessage.error('删除失败')
    }
  }

  function openPatternDialog(item?: SandboxDangerousPattern) {
    if (item) {
      editingPatternId.value = item.id
      patternForm.value = { pattern: item.pattern, description: item.description, scope: item.scope }
    } else {
      editingPatternId.value = null
      patternForm.value = { pattern: '', description: '', scope: 'server' }
    }
    showPatternDialog.value = true
  }

  async function handleSavePattern() {
    try {
      if (editingPatternId.value) {
        const updated = await updateDangerousPattern(editingPatternId.value, patternForm.value)
        const idx = dangerousPatterns.value.findIndex(p => p.id === editingPatternId.value)
        if (idx >= 0) dangerousPatterns.value[idx] = updated
        ElMessage.success('已更新')
      } else {
        const created = await addDangerousPattern(patternForm.value)
        dangerousPatterns.value.push(created)
        ElMessage.success('已添加')
      }
      showPatternDialog.value = false
    } catch {
      ElMessage.error('操作失败')
    }
  }

  async function handleDeletePattern(id: string) {
    try {
      await ElMessageBox.confirm('确定要删除该危险命令模式吗？', '删除确认', { type: 'warning' })
      await deleteDangerousPattern(id)
      dangerousPatterns.value = dangerousPatterns.value.filter(p => p.id !== id)
      ElMessage.success('已删除')
    } catch { /* cancelled */ }
  }

  function openBlacklistDialog(item?: SandboxCommandItem) {
    if (item) {
      editingBlacklistId.value = item.id
      blacklistForm.value = { command: item.command, scope: item.scope }
    } else {
      editingBlacklistId.value = null
      blacklistForm.value = { command: '', scope: 'server' }
    }
    showBlacklistDialog.value = true
  }

  async function handleSaveBlacklist() {
    try {
      if (editingBlacklistId.value) {
        const updated = await updateBlacklistItem(editingBlacklistId.value, blacklistForm.value)
        const idx = blacklist.value.findIndex(b => b.id === editingBlacklistId.value)
        if (idx >= 0) blacklist.value[idx] = updated
        ElMessage.success('已更新')
      } else {
        const created = await addBlacklistItem(blacklistForm.value)
        blacklist.value.push(created)
        ElMessage.success('已添加')
      }
      showBlacklistDialog.value = false
    } catch {
      ElMessage.error('操作失败')
    }
  }

  async function handleDeleteBlacklist(id: string) {
    try {
      await deleteBlacklistItem(id)
      blacklist.value = blacklist.value.filter(b => b.id !== id)
      ElMessage.success('已删除')
    } catch {
      ElMessage.error('删除失败')
    }
  }

  function openWhitelistDialog(item?: SandboxCommandItem) {
    if (item) {
      editingWhitelistId.value = item.id
      whitelistForm.value = { command: item.command, scope: item.scope }
    } else {
      editingWhitelistId.value = null
      whitelistForm.value = { command: '', scope: 'server' }
    }
    showWhitelistDialog.value = true
  }

  async function handleSaveWhitelist() {
    try {
      if (editingWhitelistId.value) {
        const updated = await updateWhitelistItem(editingWhitelistId.value, whitelistForm.value)
        const idx = whitelist.value.findIndex(w => w.id === editingWhitelistId.value)
        if (idx >= 0) whitelist.value[idx] = updated
        ElMessage.success('已更新')
      } else {
        const created = await addWhitelistItem(whitelistForm.value)
        whitelist.value.push(created)
        ElMessage.success('已添加')
      }
      showWhitelistDialog.value = false
    } catch {
      ElMessage.error('操作失败')
    }
  }

  async function handleDeleteWhitelist(id: string) {
    try {
      await deleteWhitelistItem(id)
      whitelist.value = whitelist.value.filter(w => w.id !== id)
      ElMessage.success('已删除')
    } catch {
      ElMessage.error('删除失败')
    }
  }

  onMounted(() => { void loadConfig() })

  return {
    loading, saving, config, form, paths, dangerousPatterns, blacklist, whitelist,
    showPathDialog, newPath,
    showPatternDialog, editingPatternId, patternForm,
    showBlacklistDialog, editingBlacklistId, blacklistForm,
    showWhitelistDialog, editingWhitelistId, whitelistForm,
    loadConfig, saveSettings, resetForm,
    handleAddPath, handleDeletePath,
    openPatternDialog, handleSavePattern, handleDeletePattern,
    openBlacklistDialog, handleSaveBlacklist, handleDeleteBlacklist,
    openWhitelistDialog, handleSaveWhitelist, handleDeleteWhitelist,
  }
}
