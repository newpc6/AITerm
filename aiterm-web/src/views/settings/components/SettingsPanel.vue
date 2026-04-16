<script setup lang="ts">
import type { LLMSettingsData, LLMSettingsPayload } from '@/types/api'

defineProps<{
  commandBlacklistText: string
  commandWhitelistText: string
  form: LLMSettingsPayload
  loading: boolean
  saving: boolean
  settings: LLMSettingsData | null
}>()

const emit = defineEmits<{
  reset: []
  save: []
  'update:commandBlacklistText': [value: string]
  'update:commandWhitelistText': [value: string]
}>()
</script>

<template>
  <div class="settings-panel">
    <el-alert
      v-if="settings?.api_url && (settings.api_url.includes('127.0.0.1') || settings.api_url.includes('localhost'))"
      title="当前模型地址指向本地服务，请确认对应的大模型服务正在运行。" type="warning" show-icon :closable="false" />

    <el-form label-position="top">
      <el-form-item label="API 地址">
        <el-input v-model="form.api_url" placeholder="https://api.openai.com/v1" :disabled="loading || saving" />
      </el-form-item>

      <el-form-item label="API Key">
        <el-input v-model="form.api_key" type="password" show-password placeholder="OpenAI / 兼容服务 API Key，可为空"
          :disabled="loading || saving" />
      </el-form-item>

      <el-form-item label="模型">
        <el-input v-model="form.model" placeholder="gpt-4o-mini" :disabled="loading || saving" />
      </el-form-item>

      <el-form-item label="温度参数">
        <el-input-number v-model="form.temperature" :min="0" :max="2" :step="0.1" :precision="1"
          :disabled="loading || saving" />
      </el-form-item>

      <el-form-item label="对话系统提示词">
        <el-input v-model="form.chat_system_prompt" type="textarea" :rows="4" resize="vertical"
          placeholder="可使用 {{node_description}}、{{user_request}} 等占位符" :disabled="loading || saving" />
      </el-form-item>

      <el-form-item label="任务规划提示词">
        <el-input v-model="form.task_planner_prompt" type="textarea" :rows="8" resize="vertical"
          placeholder="可使用 {{node_description}}、{{user_request}} 等占位符" :disabled="loading || saving" />
      </el-form-item>

      <el-form-item label="任务规划用户提示词">
        <el-input v-model="form.task_planner_user_prompt" type="textarea" :rows="10" resize="vertical"
          placeholder="可使用 {{user_request}}、{{conversation_history}}、{{platform_name}}、{{platform_tool_prompt}} 等占位符" :disabled="loading || saving" />
      </el-form-item>

      <el-form-item label="Windows 工具提示词">
        <el-input v-model="form.task_windows_tool_prompt" type="textarea" :rows="8" resize="vertical"
          placeholder="告诉模型在 Windows 上下载、删除、移动、查找、查看文件等常见操作优先使用哪些命令"
          :disabled="loading || saving" />
      </el-form-item>

      <el-form-item label="Linux 工具提示词">
        <el-input v-model="form.task_linux_tool_prompt" type="textarea" :rows="8" resize="vertical"
          placeholder="告诉模型在 Linux 上下载、删除、移动、查找、查看文件等常见操作优先使用哪些命令"
          :disabled="loading || saving" />
      </el-form-item>

      <el-form-item label="macOS 工具提示词">
        <el-input v-model="form.task_mac_tool_prompt" type="textarea" :rows="8" resize="vertical"
          placeholder="告诉模型在 macOS 上下载、删除、移动、查找、查看文件等常见操作优先使用哪些命令"
          :disabled="loading || saving" />
      </el-form-item>

      <el-form-item label="任务失败修正提示词">
        <el-input v-model="form.task_failure_repair_prompt" type="textarea" :rows="10" resize="vertical"
          placeholder="可使用 {{user_request}}、{{step_title}}、{{failed_command}}、{{execution_output}}、{{failure_text}} 等占位符"
          :disabled="loading || saving" />
      </el-form-item>

      <el-form-item label="任务命令风控规则提示词">
        <el-input v-model="form.task_command_rules_prompt" type="textarea" :rows="5" resize="vertical"
          placeholder="可使用 {{command_rules}}、{{blacklist}}、{{whitelist}} 等占位符" :disabled="loading || saving" />
      </el-form-item>

      <el-form-item label="任务命令黑名单">
        <el-input :model-value="commandBlacklistText" type="textarea" :rows="6" resize="vertical"
          placeholder="每行一条规则，命中后任务必须人工确认，例如 delete、rm、shutdown" :disabled="loading || saving"
          @update:model-value="emit('update:commandBlacklistText', $event)" />
      </el-form-item>

      <el-form-item label="任务命令白名单">
        <el-input :model-value="commandWhitelistText" type="textarea" :rows="4" resize="vertical"
          placeholder="每行一条规则，命中后可跳过黑名单误判，例如安全查询命令" :disabled="loading || saving"
          @update:model-value="emit('update:commandWhitelistText', $event)" />
      </el-form-item>
    </el-form>

    <el-descriptions v-if="settings" :column="1" border>
      <el-descriptions-item label="已配置">
        {{ settings.configured ? "是" : "否" }}
      </el-descriptions-item>
      <el-descriptions-item label="当前地址">
        {{ settings.api_url || '未设置' }}
      </el-descriptions-item>
      <el-descriptions-item label="当前模型">
        {{ settings.model || '未设置' }}
      </el-descriptions-item>
      <el-descriptions-item label="API Key">
        {{ settings.api_key ? '已设置' : '未设置' }}
      </el-descriptions-item>
      <el-descriptions-item label="对话提示词">
        {{ settings.chat_system_prompt ? '已设置' : '未设置' }}
      </el-descriptions-item>
      <el-descriptions-item label="任务规划提示词">
        {{ settings.task_planner_prompt ? '已设置' : '未设置' }}
      </el-descriptions-item>
      <el-descriptions-item label="任务规划用户提示词">
        {{ settings.task_planner_user_prompt ? '已设置' : '未设置' }}
      </el-descriptions-item>
      <el-descriptions-item label="Windows 工具提示词">
        {{ settings.task_windows_tool_prompt ? '已设置' : '未设置' }}
      </el-descriptions-item>
      <el-descriptions-item label="Linux 工具提示词">
        {{ settings.task_linux_tool_prompt ? '已设置' : '未设置' }}
      </el-descriptions-item>
      <el-descriptions-item label="macOS 工具提示词">
        {{ settings.task_mac_tool_prompt ? '已设置' : '未设置' }}
      </el-descriptions-item>
      <el-descriptions-item label="任务失败修正提示词">
        {{ settings.task_failure_repair_prompt ? '已设置' : '未设置' }}
      </el-descriptions-item>
      <el-descriptions-item label="任务命令风控规则提示词">
        {{ settings.task_command_rules_prompt ? '已设置' : '未设置' }}
      </el-descriptions-item>
      <el-descriptions-item label="任务命令黑名单">
        <div v-if="settings.task_command_blacklist.length" class="settings-panel__rules">
          <code v-for="item in settings.task_command_blacklist" :key="`black-${item}`">{{ item }}</code>
        </div>
        <span v-else>未设置</span>
      </el-descriptions-item>
      <el-descriptions-item label="任务命令白名单">
        <div v-if="settings.task_command_whitelist.length" class="settings-panel__rules">
          <code v-for="item in settings.task_command_whitelist" :key="`white-${item}`">{{ item }}</code>
        </div>
        <span v-else>未设置</span>
      </el-descriptions-item>
    </el-descriptions>

    <div class="settings-panel__actions">
      <el-button :disabled="loading || saving" @click="emit('reset')">重置</el-button>
      <el-button type="primary" :loading="saving" @click="emit('save')">保存</el-button>
    </div>
  </div>
</template>

<style scoped>
.settings-panel {
  display: grid;
  gap: 20px;
}

.settings-panel__actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.settings-panel__rules {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.settings-panel__rules code {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.06);
  overflow-wrap: anywhere;
}
</style>
