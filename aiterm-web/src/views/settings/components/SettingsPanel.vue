<script setup lang="ts">
import { ref } from 'vue'
import type { GlobalSettingsData, GlobalSettingsPayload } from '@/types/api'

const props = defineProps<{
  form: GlobalSettingsPayload
  loading: boolean
  saving: boolean
  settings: GlobalSettingsData | null
}>()

const emit = defineEmits<{
  reset: []
  save: []
}>()

const showBlacklistDialog = ref(false)
const showWhitelistDialog = ref(false)
const newBlacklistItem = ref('')
const newWhitelistItem = ref('')

function removeBlacklistItem(index: number) {
  props.form.execution_command_blacklist?.splice(index, 1)
}

function removeWhitelistItem(index: number) {
  props.form.execution_command_whitelist?.splice(index, 1)
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
  if (props.form.execution_command_blacklist?.includes(item)) {
    return
  }
  props.form.execution_command_blacklist = props.form.execution_command_blacklist || []
  props.form.execution_command_blacklist.push(item)
  showBlacklistDialog.value = false
  newBlacklistItem.value = ''
}

function addWhitelistItem() {
  const item = newWhitelistItem.value.trim()
  if (!item) return
  if (props.form.execution_command_whitelist?.includes(item)) {
    return
  }
  props.form.execution_command_whitelist = props.form.execution_command_whitelist || []
  props.form.execution_command_whitelist.push(item)
  showWhitelistDialog.value = false
  newWhitelistItem.value = ''
}
</script>

<template>
  <div class="settings-panel">
    <el-alert
      v-if="settings?.api_url && (settings.api_url.includes('127.0.0.1') || settings.api_url.includes('localhost'))"
      title="当前模型地址指向本地服务，请确认对应的大模型服务正在运行。" type="warning" show-icon :closable="false" />

    <el-form label-position="top">
      <el-form-item label="意图识别提示词">
        <el-input v-model="form.intent_detection_prompt" type="textarea" :rows="6" resize="vertical"
          placeholder="可使用 {{user_message}} 占位符，返回 JSON 格式 {\"intent\": \"chat\"} 或 {\"intent\": \"execute\"}" :disabled="loading || saving" />
      </el-form-item>

      <el-form-item label="对话系统提示词">
        <el-input v-model="form.chat_system_prompt" type="textarea" :rows="4" resize="vertical"
          placeholder="可使用 {{node_description}}、{{user_request}} 等占位符" :disabled="loading || saving" />
      </el-form-item>

      <el-form-item label="执行规划提示词">
        <el-input v-model="form.execution_planner_prompt" type="textarea" :rows="8" resize="vertical"
          placeholder="可使用 {{node_description}}、{{user_request}} 等占位符" :disabled="loading || saving" />
      </el-form-item>

      <el-form-item label="执行规划用户提示词">
        <el-input v-model="form.execution_planner_user_prompt" type="textarea" :rows="10" resize="vertical"
          placeholder="可使用 {{user_request}}、{{conversation_history}}、{{platform_name}}、{{platform_tool_prompt}} 等占位符" :disabled="loading || saving" />
      </el-form-item>

      <el-form-item label="Windows 工具提示词">
        <el-input v-model="form.execution_windows_tool_prompt" type="textarea" :rows="8" resize="vertical"
          placeholder="告诉模型在 Windows 上下载、删除、移动、查找、查看文件等常见操作优先使用哪些命令"
          :disabled="loading || saving" />
      </el-form-item>

      <el-form-item label="Linux 工具提示词">
        <el-input v-model="form.execution_linux_tool_prompt" type="textarea" :rows="8" resize="vertical"
          placeholder="告诉模型在 Linux 上下载、删除、移动、查找、查看文件等常见操作优先使用哪些命令"
          :disabled="loading || saving" />
      </el-form-item>

      <el-form-item label="macOS 工具提示词">
        <el-input v-model="form.execution_mac_tool_prompt" type="textarea" :rows="8" resize="vertical"
          placeholder="告诉模型在 macOS 上下载、删除、移动、查找、查看文件等常见操作优先使用哪些命令"
          :disabled="loading || saving" />
      </el-form-item>

      <el-form-item label="执行失败修正提示词">
        <el-input v-model="form.execution_failure_repair_prompt" type="textarea" :rows="10" resize="vertical"
          placeholder="可使用 {{user_request}}、{{step_title}}、{{failed_command}}、{{execution_output}}、{{failure_text}} 等占位符"
          :disabled="loading || saving" />
      </el-form-item>

      <el-form-item label="命令风控规则提示词">
        <el-input v-model="form.execution_command_rules_prompt" type="textarea" :rows="5" resize="vertical"
          placeholder="可使用 {{command_rules}}、{{blacklist}}、{{whitelist}} 等占位符" :disabled="loading || saving" />
      </el-form-item>

      <el-form-item label="命令黑名单">
        <div class="tag-container">
          <el-tag
            v-for="(item, index) in form.execution_command_blacklist"
            :key="index"
            type="danger"
            closable
            :disable-transitions="false"
            @close="removeBlacklistItem(index)"
            class="rule-tag"
          >
            {{ item }}
          </el-tag>
          <el-button size="small" type="primary" plain @click="openBlacklistDialog" :disabled="loading || saving">
            + 添加
          </el-button>
        </div>
        <div class="tag-hint">命中黑名单的命令需要人工确认后才会执行</div>
      </el-form-item>

      <el-form-item label="命令白名单">
        <div class="tag-container">
          <el-tag
            v-for="(item, index) in form.execution_command_whitelist"
            :key="index"
            type="success"
            closable
            :disable-transitions="false"
            @close="removeWhitelistItem(index)"
            class="rule-tag"
          >
            {{ item }}
          </el-tag>
          <el-button size="small" type="primary" plain @click="openWhitelistDialog" :disabled="loading || saving">
            + 添加
          </el-button>
        </div>
        <div class="tag-hint">命中白名单的命令可跳过黑名单检测</div>
      </el-form-item>

      <el-form-item label="LLM 调试日志">
        <el-switch
          v-model="form.llm_debug_logging"
          :disabled="loading || saving"
          active-text="开启"
          inactive-text="关闭"
        />
        <div class="tag-hint">开启后会在控制台打印大模型调用的输入输出，方便排查问题</div>
      </el-form-item>
    </el-form>

    <el-descriptions v-if="settings" :column="1" border>
      <el-descriptions-item label="意图识别提示词">
        {{ settings.intent_detection_prompt ? '已设置' : '未设置' }}
      </el-descriptions-item>
      <el-descriptions-item label="对话提示词">
        {{ settings.chat_system_prompt ? '已设置' : '未设置' }}
      </el-descriptions-item>
      <el-descriptions-item label="执行规划提示词">
        {{ settings.execution_planner_prompt ? '已设置' : '未设置' }}
      </el-descriptions-item>
      <el-descriptions-item label="执行规划用户提示词">
        {{ settings.execution_planner_user_prompt ? '已设置' : '未设置' }}
      </el-descriptions-item>
      <el-descriptions-item label="Windows 工具提示词">
        {{ settings.execution_windows_tool_prompt ? '已设置' : '未设置' }}
      </el-descriptions-item>
      <el-descriptions-item label="Linux 工具提示词">
        {{ settings.execution_linux_tool_prompt ? '已设置' : '未设置' }}
      </el-descriptions-item>
      <el-descriptions-item label="macOS 工具提示词">
        {{ settings.execution_mac_tool_prompt ? '已设置' : '未设置' }}
      </el-descriptions-item>
      <el-descriptions-item label="执行失败修正提示词">
        {{ settings.execution_failure_repair_prompt ? '已设置' : '未设置' }}
      </el-descriptions-item>
      <el-descriptions-item label="命令风控规则提示词">
        {{ settings.execution_command_rules_prompt ? '已设置' : '未设置' }}
      </el-descriptions-item>
      <el-descriptions-item label="命令黑名单">
        <div v-if="settings.execution_command_blacklist.length" class="tag-container">
          <el-tag v-for="item in settings.execution_command_blacklist" :key="`black-${item}`" type="danger" size="small">
            {{ item }}
          </el-tag>
        </div>
        <span v-else>未设置</span>
      </el-descriptions-item>
      <el-descriptions-item label="命令白名单">
        <div v-if="settings.execution_command_whitelist.length" class="tag-container">
          <el-tag v-for="item in settings.execution_command_whitelist" :key="`white-${item}`" type="success" size="small">
            {{ item }}
          </el-tag>
        </div>
        <span v-else>未设置</span>
      </el-descriptions-item>
    </el-descriptions>

    <div class="settings-panel__actions">
      <el-button :disabled="loading || saving" @click="emit('reset')">重置</el-button>
      <el-button type="primary" :loading="saving" @click="emit('save')">保存</el-button>
    </div>
  </div>

  <el-dialog v-model="showBlacklistDialog" title="添加黑名单规则" width="400px">
    <el-form @submit.prevent="addBlacklistItem">
      <el-form-item label="命令关键词">
        <el-input
          v-model="newBlacklistItem"
          placeholder="例如：rm、del、shutdown"
          @keyup.enter="addBlacklistItem"
          autofocus
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showBlacklistDialog = false">取消</el-button>
      <el-button type="primary" @click="addBlacklistItem">添加</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="showWhitelistDialog" title="添加白名单规则" width="400px">
    <el-form @submit.prevent="addWhitelistItem">
      <el-form-item label="命令关键词">
        <el-input
          v-model="newWhitelistItem"
          placeholder="例如：ls、dir、cat"
          @keyup.enter="addWhitelistItem"
          autofocus
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showWhitelistDialog = false">取消</el-button>
      <el-button type="primary" @click="addWhitelistItem">添加</el-button>
    </template>
  </el-dialog>
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

.tag-container {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.rule-tag {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tag-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
