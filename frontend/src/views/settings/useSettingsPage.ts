import { computed, onMounted, ref } from 'vue'

import { getAuthSettings, getGlobalSettings, updateAuthSettings, updateGlobalSettings } from '@/api/aiterm'
import type { AuthSettingsData, AuthSettingsPayload, GlobalSettingsData, GlobalSettingsPayload } from '@/types/api'

export function useSettingsPage() {
  const loading = ref(false)
  const saving = ref(false)
  const authSaving = ref(false)
  const errorMessage = ref('')
  const successMessage = ref('')
  const settings = ref<GlobalSettingsData | null>(null)
  const authSettings = ref<AuthSettingsData | null>(null)
  const form = ref<GlobalSettingsPayload>({
    chat_system_prompt: '',
    chat_history_limit: 12,
    execution_command_blacklist: [],
    execution_command_whitelist: [],
    llm_debug_logging: false,
  })
  const commandBlacklistText = ref('')
  const commandWhitelistText = ref('')
  const authForm = ref<AuthSettingsPayload>({
    enabled: false,
    allow_password_login: true,
    session_ttl_hours: 24,
  })

  function syncForm(data: GlobalSettingsData) {
    form.value = {
      chat_system_prompt: data.chat_system_prompt,
      chat_history_limit: data.chat_history_limit,
      execution_command_blacklist: data.execution_command_blacklist ?? [],
      execution_command_whitelist: data.execution_command_whitelist ?? [],
      llm_debug_logging: data.llm_debug_logging ?? false,
    }
    commandBlacklistText.value = (data.execution_command_blacklist ?? []).join('\n')
    commandWhitelistText.value = (data.execution_command_whitelist ?? []).join('\n')
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
      settings.value = await getGlobalSettings()
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
      settings.value = await updateGlobalSettings({
        ...form.value,
        execution_command_blacklist: parseCommandRuleText(commandBlacklistText.value),
        execution_command_whitelist: parseCommandRuleText(commandWhitelistText.value),
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

  const currentModel = computed(() => '提示词配置')

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
