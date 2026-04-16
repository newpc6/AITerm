import { computed, onMounted, ref } from 'vue'

import { getAuthSettings, getLLMSettings, updateAuthSettings, updateLLMSettings } from '@/api/aiterm'
import type { AuthSettingsData, AuthSettingsPayload, LLMSettingsData, LLMSettingsPayload } from '@/types/api'

export function useSettingsPage() {
  const loading = ref(false)
  const saving = ref(false)
  const authSaving = ref(false)
  const errorMessage = ref('')
  const successMessage = ref('')
  const settings = ref<LLMSettingsData | null>(null)
  const authSettings = ref<AuthSettingsData | null>(null)
  const form = ref<LLMSettingsPayload>({
    api_url: '',
    api_key: '',
    model: '',
    temperature: 0.7,
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
  const authForm = ref<AuthSettingsPayload>({
    enabled: false,
    allow_password_login: true,
    session_ttl_hours: 24,
  })

  function syncForm(data: LLMSettingsData) {
    form.value = {
      api_url: data.api_url,
      api_key: data.api_key,
      model: data.model,
      temperature: data.temperature,
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

  function syncAuthForm(data: AuthSettingsData) {
    authForm.value = {
      enabled: data.enabled,
      allow_password_login: data.allow_password_login,
      session_ttl_hours: data.session_ttl_hours,
    }
  }

  async function loadSettings() {
    loading.value = true
    errorMessage.value = ''

    try {
      settings.value = await getLLMSettings()
      syncForm(settings.value)
      authSettings.value = await getAuthSettings()
      syncAuthForm(authSettings.value)
    } catch {
      errorMessage.value = '设置接口不可用。'
    } finally {
      loading.value = false
    }
  }

  async function saveSettings() {
    saving.value = true
    errorMessage.value = ''
    successMessage.value = ''

    try {
      settings.value = await updateLLMSettings({
        ...form.value,
        task_command_blacklist: parseCommandRuleText(commandBlacklistText.value),
        task_command_whitelist: parseCommandRuleText(commandWhitelistText.value),
      })
      syncForm(settings.value)
      successMessage.value = '设置保存成功。'
    } catch {
      errorMessage.value = '保存设置失败。'
    } finally {
      saving.value = false
    }
  }

  async function saveAuthConfig() {
    authSaving.value = true
    errorMessage.value = ''
    successMessage.value = ''

    try {
      authSettings.value = await updateAuthSettings(authForm.value)
      syncAuthForm(authSettings.value)
      successMessage.value = '登录设置保存成功。'
    } catch {
      errorMessage.value = '保存登录设置失败。'
    } finally {
      authSaving.value = false
    }
  }

  function resetForm() {
    if (!settings.value) {
      return
    }

    syncForm(settings.value)
    successMessage.value = ''
    errorMessage.value = ''
  }

  function resetAuthForm() {
    if (!authSettings.value) {
      return
    }

    syncAuthForm(authSettings.value)
    successMessage.value = ''
    errorMessage.value = ''
  }

  const currentModel = computed(() => form.value.model || '未配置')

  onMounted(() => {
    void loadSettings()
  })

  return {
    errorMessage,
    authForm,
    authSaving,
    authSettings,
    form,
    loading,
    commandBlacklistText,
    commandWhitelistText,
    currentModel,
    loadSettings,
    resetAuthForm,
    resetForm,
    saveAuthConfig,
    saveSettings,
    saving,
    settings,
    successMessage,
  }
}
