import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { getGlobalSettings, updateGlobalSettings } from '@/api/aiterm'
import type { GlobalSettingsData, GlobalSettingsPayload } from '@/types/api'

export function useGlobalSettingsPage() {
  const loading = ref(false)
  const saving = ref(false)
  const settings = ref<GlobalSettingsData | null>(null)
  const form = ref<GlobalSettingsPayload>({
    intent_detection_prompt: '',
    chat_system_prompt: '',
    chat_history_limit: 12,
    execution_planner_prompt: '',
    execution_planner_user_prompt: '',
    execution_windows_tool_prompt: '',
    execution_linux_tool_prompt: '',
    execution_mac_tool_prompt: '',
    execution_failure_repair_prompt: '',
    execution_command_rules_prompt: '',
    execution_command_blacklist: [],
    execution_command_whitelist: [],
  })

  const showBlacklistDialog = ref(false)
  const showWhitelistDialog = ref(false)
  const newBlacklistItem = ref('')
  const newWhitelistItem = ref('')

  function syncForm(data: GlobalSettingsData) {
    form.value = {
      intent_detection_prompt: data.intent_detection_prompt,
      chat_system_prompt: data.chat_system_prompt,
      chat_history_limit: data.chat_history_limit,
      execution_planner_prompt: data.execution_planner_prompt,
      execution_planner_user_prompt: data.execution_planner_user_prompt,
      execution_windows_tool_prompt: data.execution_windows_tool_prompt,
      execution_linux_tool_prompt: data.execution_linux_tool_prompt,
      execution_mac_tool_prompt: data.execution_mac_tool_prompt,
      execution_failure_repair_prompt: data.execution_failure_repair_prompt,
      execution_command_rules_prompt: data.execution_command_rules_prompt,
      execution_command_blacklist: data.execution_command_blacklist ?? [],
      execution_command_whitelist: data.execution_command_whitelist ?? [],
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
    newBlacklistItem,
    newWhitelistItem,
    loadSettings,
    saveSettings,
    resetForm,
    removeBlacklistItem,
    removeWhitelistItem,
    openBlacklistDialog,
    openWhitelistDialog,
    addBlacklistItem,
    addWhitelistItem,
  }
}
