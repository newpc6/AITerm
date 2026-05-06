<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { createShare, getShareByChat, deleteShareByChat, type ShareItem } from '@/api/aiterm'

const props = defineProps<{
  chatId: string
  chatTitle?: string
}>()

const emit = defineEmits<{
  close: []
}>()

const visible = ref(true)
const loading = ref(false)
const existingShare = ref<ShareItem | null>(null)
const shareLink = ref('')

const form = ref({
  title: '',
  password: '',
  expiresIn: 0,
  showInput: true,
  showThinking: true,
  showTools: true,
  showAnswer: true,
  showFullInput: false,
})

const expiresInOptions = [
  { label: '永不过期', value: 0 },
  { label: '1小时', value: 3600 },
  { label: '1天', value: 86400 },
  { label: '7天', value: 604800 },
  { label: '30天', value: 2592000 },
]

const shareCreated = ref(false)

const shareFullInfo = computed(() => {
  if (!existingShare.value) return ''
  let info = `分享链接：${shareLink.value}`
  if (form.value.password) {
    info += `\n访问密码：${form.value.password}`
  }
  if (existingShare.value.expires_at) {
    info += `\n有效期至：${new Date(existingShare.value.expires_at).toLocaleString()}`
  }
  return info
})

async function loadExistingShare() {
  if (!props.chatId) return
  try {
    const share = await getShareByChat(props.chatId)
    if (share) {
      existingShare.value = share
      shareLink.value = `${window.location.origin}/share/${share.share_id}`
      shareCreated.value = true
    }
  } catch {
    // No existing share
  }
}

loadExistingShare()

async function handleCreateShare() {
  if (!props.chatId) {
    ElMessage.warning('请先创建对话')
    return
  }

  loading.value = true
  try {
    const payload: {
      chat_id: string
      title?: string
      password?: string
      expires_in?: number
      show_input?: boolean
      show_thinking?: boolean
      show_tools?: boolean
      show_answer?: boolean
      show_full_input?: boolean
    } = {
      chat_id: props.chatId,
      show_input: form.value.showInput,
      show_thinking: form.value.showThinking,
      show_tools: form.value.showTools,
      show_answer: form.value.showAnswer,
      show_full_input: form.value.showFullInput,
    }

    if (form.value.title.trim()) {
      payload.title = form.value.title.trim()
    }

    if (form.value.password.trim()) {
      payload.password = form.value.password.trim()
    }

    if (form.value.expiresIn > 0) {
      payload.expires_in = form.value.expiresIn
    }

    const share = await createShare(payload)
    existingShare.value = share
    shareLink.value = `${window.location.origin}/share/${share.share_id}`
    shareCreated.value = true
    ElMessage.success('分享链接已生成')
  } catch (e: unknown) {
    const err = e as { response?: { data?: { message?: string } } }
    ElMessage.error(err?.response?.data?.message || '创建分享失败')
  } finally {
    loading.value = false
  }
}

async function handleDeleteShare() {
  if (!existingShare.value) return

  loading.value = true
  try {
    await deleteShareByChat(props.chatId)
    existingShare.value = null
    shareLink.value = ''
    shareCreated.value = false
    ElMessage.success('分享已取消')
  } catch {
    ElMessage.error('取消分享失败')
  } finally {
    loading.value = false
  }
}

async function copyLink() {
  if (!shareLink.value) return
  try {
    await navigator.clipboard.writeText(shareLink.value)
    ElMessage.success('链接已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

async function copyFullInfo() {
  if (!shareFullInfo.value) return
  try {
    await navigator.clipboard.writeText(shareFullInfo.value)
    ElMessage.success('分享信息已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

function openSharePage() {
  if (shareLink.value) {
    window.open(shareLink.value, '_blank')
  }
}

function handleClose() {
  emit('close')
}
</script>

<template>
  <el-dialog v-model="visible" title="分享对话" width="520px" :close-on-click-modal="false" @close="handleClose">
    <template v-if="!shareCreated">
      <el-form label-width="80px">
        <el-form-item label="标题">
          <el-input v-model="form.title" :placeholder="chatTitle || '分享标题'" />
        </el-form-item>
        <el-form-item label="访问密码">
          <el-input v-model="form.password" type="password" placeholder="留空则无需密码" show-password />
        </el-form-item>
        <el-form-item label="有效期">
          <el-select v-model="form.expiresIn" style="width: 100%">
            <el-option v-for="opt in expiresInOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="展示内容">
          <div class="share-checkbox-group">
            <el-checkbox v-model="form.showInput">输入</el-checkbox>
            <el-checkbox v-model="form.showThinking">思考</el-checkbox>
            <el-checkbox v-model="form.showTools">工具调用</el-checkbox>
            <el-checkbox v-model="form.showAnswer">回答</el-checkbox>
            <el-checkbox v-model="form.showFullInput">完整输入</el-checkbox>
          </div>
        </el-form-item>
      </el-form>
    </template>

    <template v-else>
      <div class="share-result">
        <div class="share-result__label">分享链接</div>
        <div class="share-result__link">
          <el-input :model-value="shareLink" readonly>
            <template #append>
              <el-button-group>
                <el-button @click="copyLink">复制</el-button>
                <el-button @click="openSharePage">打开</el-button>
              </el-button-group>
            </template>
          </el-input>
        </div>

        <div class="share-result__full-info">
          <div class="share-result__label">完整分享信息</div>
          <el-input :model-value="shareFullInfo" type="textarea" :rows="4" readonly />
          <el-button class="share-result__copy-btn" text type="primary" @click="copyFullInfo">复制分享信息</el-button>
        </div>

        <div class="share-result__info">
          <span v-if="existingShare?.has_password">已设置访问密码</span>
          <span v-if="existingShare?.expires_at">
            有效期至：{{ new Date(existingShare.expires_at).toLocaleString() }}
          </span>
          <span v-if="!existingShare?.expires_at">永不过期</span>
        </div>
        <div class="share-result__actions">
          <el-button type="danger" text @click="handleDeleteShare">取消分享</el-button>
        </div>
      </div>
    </template>

    <template #footer>
      <template v-if="!shareCreated">
        <el-button @click="handleClose">取消</el-button>
        <el-button type="primary" :loading="loading" @click="handleCreateShare">创建分享</el-button>
      </template>
      <template v-else>
        <el-button type="primary" @click="handleClose">完成</el-button>
      </template>
    </template>
  </el-dialog>
</template>

<style scoped>
.share-result {
  padding: 8px 0;
}

.share-result__label {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.share-result__link {
  margin-bottom: 16px;
}

.share-result__full-info {
  margin-bottom: 16px;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
}

.share-result__copy-btn {
  margin-top: 8px;
}

.share-result__info {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  display: flex;
  gap: 16px;
}

.share-result__actions {
  margin-top: 16px;
  text-align: right;
}

.share-checkbox-group {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}
</style>
