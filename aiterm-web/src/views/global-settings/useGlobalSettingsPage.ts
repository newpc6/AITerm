import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { getGlobalSettings, updateGlobalSettings } from '@/api/aiterm'
import type { GlobalSettingsData, GlobalSettingsPayload } from '@/types/api'

export function useGlobalSettingsPage() {
  const loading = ref(false)
  const saving = ref(false)
  const settings = ref<GlobalSettingsData | null>(null)
  const form = ref<GlobalSettingsPayload>({
    chat_system_prompt: '',
    task_planner_prompt: '',
    task_planner_user_prompt: '',
    task_windows_tool_prompt: '',
    task_linux_tool_prompt: '',
    task_mac_tool_prompt: '',
    task_failure_repair_prompt: '',
    task_command_rules_prompt: '',
    task_command_blacklist: [],
    task_command_whitelist: [],
  })
  const commandBlacklistText = ref('')
  const commandWhitelistText = ref('')

  function syncForm(data: GlobalSettingsData) {
    form.value = {
      chat_system_prompt: data.chat_system_prompt,
      task_planner_prompt: data.task_planner_prompt,
      task_planner_user_prompt: data.task_planner_user_prompt,
      task_windows_tool_prompt: data.task_windows_tool_prompt,
      task_linux_tool_prompt: data.task_linux_tool_prompt,
      task_mac_tool_prompt: data.task_mac_tool_prompt,
      task_failure_repair_prompt: data.task_failure_repair_prompt,
      task_command_rules_prompt: data.task_command_rules_prompt,
      task_command_blacklist: data.task_command_blacklist ?? [],
      task_command_whitelist: data.task_command_whitelist ?? [],
    }
    commandBlacklistText.value = (data.task_command_blacklist ?? []).join('\n')
    commandWhitelistText.value = (data.task_command_whitelist ?? []).join('\n')
  }

  function parseCommandRuleText(value: string) {
    return value
      .split(/\r?\n/)
      .map((item) => item.trim())
      .filter(Boolean)
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
      const payload: GlobalSettingsPayload = {
        ...form.value,
        task_command_blacklist: parseCommandRuleText(commandBlacklistText.value),
        task_command_whitelist: parseCommandRuleText(commandWhitelistText.value),
      }
      settings.value = await updateGlobalSettings(payload)
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

  onMounted(() => {
    void loadSettings()
  })

  return {
    loading,
    saving,
    settings,
    form,
    commandBlacklistText,
    commandWhitelistText,
    loadSettings,
    saveSettings,
    resetForm,
  }
}
