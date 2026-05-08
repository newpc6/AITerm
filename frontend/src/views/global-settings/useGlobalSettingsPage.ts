import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { getGlobalSettings, updateGlobalSettings, selectFolder } from '@/api/aiterm'
import type { GlobalSettingsData, GlobalSettingsPayload } from '@/types/api'

export function useGlobalSettingsPage() {
  const loading = ref(false)
  const saving = ref(false)
  const settings = ref<GlobalSettingsData | null>(null)
  const form = ref<GlobalSettingsPayload>({
    chat_system_prompt: '',
    chat_history_limit: 12,
    max_iterations: 20,
    show_llm_input: false,
    execution_command_blacklist: [],
    execution_command_whitelist: [],
    sandbox_paths: [],
    sandbox_rules_prompt: '',
    llm_debug_logging: false,
  })

  const showBlacklistDialog = ref(false)
  const showWhitelistDialog = ref(false)
  const showSandboxDialog = ref(false)
  const newBlacklistItem = ref('')
  const newWhitelistItem = ref('')
  const newSandboxPath = ref('')

  function syncForm(data: GlobalSettingsData) {
    form.value = {
      chat_system_prompt: data.chat_system_prompt,
      chat_history_limit: data.chat_history_limit,
      max_iterations: data.max_iterations,
      show_llm_input: data.show_llm_input,
      execution_command_blacklist: data.execution_command_blacklist ?? [],
      execution_command_whitelist: data.execution_command_whitelist ?? [],
      sandbox_paths: data.sandbox_paths ?? [],
      sandbox_rules_prompt: data.sandbox_rules_prompt ?? '',
      llm_debug_logging: data.llm_debug_logging ?? false,
    }
  }

  async function loadSettings() {
    loading.value = true
    try {
      settings.value = await getGlobalSettings()
      syncForm(settings.value)
    } catch {
      ElMessage.error('加载全局配置失败')
    } finally {
      loading.value = false
    }
  }

  async function saveSettings() {
    saving.value = true
    try {
      settings.value = await updateGlobalSettings(form.value)
      syncForm(settings.value)
      ElMessage.success('全局配置已保存')
    } catch {
      ElMessage.error('保存全局配置失败')
    } finally {
      saving.value = false
    }
  }

  function resetForm() {
    if (!settings.value) return
    syncForm(settings.value)
  }

  function removeBlacklistItem(index: number) {
    form.value.execution_command_blacklist?.splice(index, 1)
  }

  function removeWhitelistItem(index: number) {
    form.value.execution_command_whitelist?.splice(index, 1)
  }

  function openBlacklistDialog() {
    newBlacklistItem.value = ''
    showBlacklistDialog.value = true
  }

  function openWhitelistDialog() {
    newWhitelistItem.value = ''
    showWhitelistDialog.value = true
  }

  function addBlacklistItem() {
    const item = newBlacklistItem.value.trim()
    if (!item) return
    if (form.value.execution_command_blacklist?.includes(item)) {
      ElMessage.warning('该规则已存在')
      return
    }
    form.value.execution_command_blacklist = form.value.execution_command_blacklist || []
    form.value.execution_command_blacklist.push(item)
    showBlacklistDialog.value = false
    newBlacklistItem.value = ''
  }

  function addWhitelistItem() {
    const item = newWhitelistItem.value.trim()
    if (!item) return
    if (form.value.execution_command_whitelist?.includes(item)) {
      ElMessage.warning('该规则已存在')
      return
    }
    form.value.execution_command_whitelist = form.value.execution_command_whitelist || []
    form.value.execution_command_whitelist.push(item)
    showWhitelistDialog.value = false
    newWhitelistItem.value = ''
  }

  function removeSandboxPath(index: number) {
    form.value.sandbox_paths?.splice(index, 1)
  }

  function openSandboxDialog() {
    newSandboxPath.value = ''
    showSandboxDialog.value = true
  }

  function addSandboxPath() {
    const item = newSandboxPath.value.trim()
    if (!item) return
    if (form.value.sandbox_paths?.includes(item)) {
      ElMessage.warning('该路径已存在')
      return
    }
    form.value.sandbox_paths = form.value.sandbox_paths || []
    form.value.sandbox_paths.push(item)
    showSandboxDialog.value = false
    newSandboxPath.value = ''
  }

  async function browseSandboxPath() {
    try {
      const result = await selectFolder()
      if (result.path) {
        if (form.value.sandbox_paths?.includes(result.path)) {
          ElMessage.warning('该路径已存在')
          return
        }
        form.value.sandbox_paths = form.value.sandbox_paths || []
        form.value.sandbox_paths.push(result.path)
      }
    } catch {
      ElMessage.error('打开文件夹选择对话框失败')
    }
  }

  onMounted(() => {
    void loadSettings()
  })

  return {
    loading,
    saving,
    settings,
    form,
    showBlacklistDialog,
    showWhitelistDialog,
    showSandboxDialog,
    newBlacklistItem,
    newWhitelistItem,
    newSandboxPath,
    loadSettings,
    saveSettings,
    resetForm,
    removeBlacklistItem,
    removeWhitelistItem,
    removeSandboxPath,
    openBlacklistDialog,
    openWhitelistDialog,
    openSandboxDialog,
    addBlacklistItem,
    addWhitelistItem,
    addSandboxPath,
    browseSandboxPath,
  }
}
