<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { MessageItem, MessageContent } from '@/views/chat/components/messages'
import { getAuthToken } from '@/auth'
import { getApiBaseUrl } from '@/config'
import { http } from '@/api/http'
import type { ApiResponse } from '@/types/api'
import type { ChatMessage } from '@/types/chat'

const PER_PAGE = 6

const props = defineProps<{ agentId: string; agentName: string }>()

const messages = ref<ChatMessage[]>([])
const loading = ref(false)
const hasMore = ref(true)
const streaming = ref(false)
const streamingId = ref('')
const input = ref('')
const sending = ref(false)
const containerRef = ref<HTMLElement | null>(null)
const shouldAutoScroll = ref(true)

let aborter: AbortController | null = null

function toMsg(m: { id: string; role: string; content: string; created_at: string }): ChatMessage {
  return { id: m.id, role: m.role as 'user' | 'assistant', content: m.content, createdAt: m.created_at }
}

async function loadMessages(beforeId?: string) {
  if (loading.value) return
  loading.value = true
  try {
    const params: Record<string, string> = { limit: String(PER_PAGE) }
    if (beforeId) params.before_id = beforeId
    const resp = await http.get<ApiResponse<{ messages: { id: string; role: string; content: string; created_at: string }[]; has_more: boolean }>>(
      '/api/v1/agents/' + props.agentId + '/messages',
      { params },
    )
    const body = resp.data as { data: { messages: { id: string; role: string; content: string; created_at: string }[]; has_more: boolean } }
    const newMsgs = (body.data.messages || []).map(toMsg)
    const more = body.data.has_more

    if (beforeId) {
      const oldH = containerRef.value ? containerRef.value.scrollHeight : 0
      messages.value = newMsgs.concat(messages.value)
      await nextTick()
      if (containerRef.value) {
        containerRef.value.scrollTop = containerRef.value.scrollHeight - oldH
      }
    } else {
      messages.value = newMsgs
      await nextTick()
      scrollToBottom()
    }
    hasMore.value = more
  } catch { /* */ }
  finally { loading.value = false }
}

function onScroll() {
  const el = containerRef.value
  if (!el) return
  shouldAutoScroll.value = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  if (el.scrollTop < 60 && hasMore.value && !loading.value) {
    const oldest = messages.value[0]
    if (oldest) loadMessages(oldest.id)
  }
}

function scrollToBottom() {
  nextTick(function () {
    if (containerRef.value) {
      containerRef.value.scrollTop = containerRef.value.scrollHeight
    }
  })
}

async function send() {
  const msg = input.value.trim()
  if (!msg || sending.value || streaming.value) return
  input.value = ''
  sending.value = true
  streaming.value = true

  const now = new Date().toISOString()
  messages.value.push({ id: '', role: 'user', content: msg, createdAt: now })
  const assistantMsg: ChatMessage = { id: now + '_a', role: 'assistant', content: '', createdAt: now }
  messages.value.push(assistantMsg)
  streamingId.value = assistantMsg.id

  await nextTick()
  scrollToBottom()

  aborter = new AbortController()

  try {
    const token = getAuthToken() || ''
    const baseUrl = getApiBaseUrl()
    const url = baseUrl + '/api/v1/agents/' + props.agentId + '/chat'
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = 'Bearer ' + token

    const resp = await fetch(url, {
      method: 'POST', signal: aborter.signal, headers,
      body: JSON.stringify({ message: msg }),
    })

    if (!resp.ok || !resp.body) throw new Error('HTTP ' + resp.status)

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let currentEvent = ''
    const dataLines: string[] = []

    function flushEvent() {
      const d = dataLines.join('\n').trim()
      dataLines.length = 0
      if (!d) { currentEvent = ''; return }
      let parsed: any
      try { parsed = JSON.parse(d) } catch { currentEvent = ''; return }

      if (currentEvent === 'delta') {
        assistantMsg.content += (parsed.delta || '')
        if (shouldAutoScroll.value) scrollToBottom()
      } else if (currentEvent === 'done') {
        assistantMsg.content = parsed.reply || assistantMsg.content
        loadMessages()
      } else if (currentEvent === 'error') {
        assistantMsg.content = '错误: ' + (parsed.error || '未知错误')
      }
      currentEvent = ''
    }

    while (true) {
      const result = await reader.read()
      buffer += decoder.decode(result.value || new Uint8Array(), { stream: !result.done })

      let idx = buffer.indexOf('\n')
      while (idx >= 0) {
        const line = buffer.slice(0, idx).replace(/\r$/, '')
        buffer = buffer.slice(idx + 1)
        if (!line.trim()) { flushEvent() }
        else if (line.startsWith('event:')) { currentEvent = line.slice(6).trim() }
        else if (line.startsWith('data:')) { dataLines.push(line.slice(5).trim()) }
        idx = buffer.indexOf('\n')
      }

      if (result.done) {
        if (buffer.trim() && buffer.trim().startsWith('data:')) {
          dataLines.push(buffer.trim().slice(5).trim())
        }
        flushEvent()
        break
      }
    }
  } catch (e: any) {
    if (e.name !== 'AbortError') {
      assistantMsg.content = '请求失败: ' + String(e)
    }
  }

  streaming.value = false
  streamingId.value = ''
  sending.value = false
  aborter = null
  scrollToBottom()
}

function stop() {
  aborter && aborter.abort()
  streaming.value = false
  streamingId.value = ''
  sending.value = false
}

onMounted(function () { loadMessages() })
onUnmounted(function () { aborter && aborter.abort() })
</script>

<template>
  <div class="agent-chat">
    <div ref="containerRef" class="agent-chat__log" @scroll="onScroll">
      <div v-if="hasMore" class="agent-chat__load-hint" :class="{ 'agent-chat__load-hint--loading': loading }">
        {{ loading ? '加载中...' : '↑ 向上滚动加载历史' }}
      </div>

      <MessageItem v-for="msg in messages" :key="msg.id || msg.createdAt" :message="msg" user-label="你"
        :assistant-label="props.agentName" :streaming-message-id="streamingId">
        <template #default="{ isStreaming }">
          <MessageContent v-if="msg.content || isStreaming" :content="msg.content" :role="msg.role"
            :is-streaming="isStreaming" />
        </template>
      </MessageItem>

      <div v-if="messages.length === 0 && !loading" class="agent-chat__empty">
        发送消息开始与 {{ props.agentName }} 对话
      </div>
    </div>

    <div class="agent-chat__input">
      <el-input v-model="input" type="textarea" :rows="2" placeholder="输入消息..." :disabled="sending" resize="none"
        @keydown.enter.exact.prevent="send()" />
      <div class="agent-chat__actions">
        <el-button v-if="streaming" type="danger" size="small" @click="stop">⏹ 停止</el-button>
        <el-button type="primary" size="small" :loading="sending" :disabled="!input.trim()"
          @click="send()">发送</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.agent-chat {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.agent-chat__log {
  flex: 1;
  overflow-y: auto;
  padding: 12px 0;
}

.agent-chat__load-hint {
  text-align: center;
  padding: 8px;
  font-size: 11px;
  color: var(--color-text-muted);
}

.agent-chat__load-hint--loading {
  color: var(--color-accent-primary);
}

.agent-chat__empty {
  text-align: center;
  padding: 40px;
  color: var(--color-text-muted);
  font-size: 13px;
}

.agent-chat__input {
  padding: 10px 12px;
  border-top: 1px solid var(--color-border-primary);
  background: var(--color-bg-secondary);
  flex-shrink: 0;
}

.agent-chat__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}
</style>
