<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue'
import { getAuthToken } from '@/auth'
import { getApiBaseUrl } from '@/config'
import { http } from '@/api/http'
import type { ApiResponse } from '@/types/api'

interface PartItem {
  type: 'input' | 'thinking' | 'tools' | 'answer'
  text?: string
  calls?: { name: string; arguments: string }[]
  _expanded?: boolean
}

interface AgentMsg {
  id: string
  role: string
  content: string
  full_input?: string
  parts: PartItem[]
  created_at: string
}

const PER_PAGE = 6

const props = defineProps<{
  agentId: string
  agentName: string
  displaySettings?: Record<string, boolean>
}>()

const messages = ref<AgentMsg[]>([])
const loading = ref(false)
const hasMore = ref(true)
const streaming = ref(false)
const streamingParts = ref<PartItem[]>([])
const streamingContent = ref('')
const input = ref('')
const sending = ref(false)
const containerRef = ref<HTMLElement | null>(null)
let aborter: AbortController | null = null

const showThinking = computed(function () { return !props.displaySettings || props.displaySettings.showThinking })
const expandThinking = computed(function () { return !!props.displaySettings?.expandThinking })
const showTools = computed(function () { return !props.displaySettings || props.displaySettings.showTools })
const expandTools = computed(function () { return !!props.displaySettings?.expandTools })
const showInput = computed(function () { return !props.displaySettings || props.displaySettings.showInput })
const showFullInput = computed(function () { return !!props.displaySettings?.showFullInput })

const shouldAutoScroll = ref(true)

async function loadMessages(beforeId?: string) {
  if (loading.value) return
  loading.value = true
  try {
    const params: Record<string, string> = { limit: String(PER_PAGE) }
    if (beforeId) params.before_id = beforeId
    const resp = await http.get<ApiResponse<{ messages: AgentMsg[]; has_more: boolean }>>('/api/v1/agents/' + props.agentId + '/messages', { params })
    const body = resp.data as { data: { messages: AgentMsg[]; has_more: boolean } }
    const newMsgs: AgentMsg[] = body.data.messages || []
    const more: boolean = body.data.has_more

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

function fmt(s: string) {
  if (!s) return ''
  try { return new Date(s).toLocaleTimeString() } catch { return '' }
}

function formatArgs(args: string): string {
  try { return JSON.stringify(JSON.parse(args), null, 2) } catch { return args }
}

async function send() {
  const msg = input.value.trim()
  if (!msg || sending.value || streaming.value) return
  input.value = ''
  sending.value = true
  streaming.value = true
  streamingParts.value = []
  streamingContent.value = ''

  const now = new Date().toISOString()
  messages.value.push({
    id: '', role: 'user', content: msg, parts: [{ type: 'input', text: msg }], created_at: now,
  })
  await nextTick()
  scrollToBottom()

  const assistantMsg: AgentMsg = {
    id: now + '_a', role: 'assistant', content: '', parts: [], created_at: now,
  }
  messages.value.push(assistantMsg)

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
    let thinkingText = ''
    let contentText = ''

    function flushEvent() {
      const d = dataLines.join('\n').trim()
      dataLines.length = 0
      if (!d) { currentEvent = ''; return }
      let parsed: any
      try { parsed = JSON.parse(d) } catch { currentEvent = ''; return }

      if (currentEvent === 'reasoning') {
        thinkingText += (parsed.delta || '')
        if (showThinking.value) {
          streamingParts.value = [
            ...streamingParts.value.filter(function (p) { return p.type !== 'thinking' }),
            { type: 'thinking', text: thinkingText },
          ]
        }
        if (shouldAutoScroll.value) scrollToBottom()
      } else if (currentEvent === 'delta') {
        contentText += (parsed.delta || '')
        streamingParts.value = streamingParts.value.filter(function (p) { return p.type !== 'answer' })
        if (contentText) {
          streamingParts.value.push({ type: 'answer', text: contentText })
        }
        assistantMsg.content = contentText
        if (shouldAutoScroll.value) scrollToBottom()
      } else if (currentEvent === 'tool_call') {
        const existing = streamingParts.value.filter(function (p) { return p.type === 'tools' })[0]
        const call = { name: parsed.tool || '', arguments: parsed.args || '' }
        if (existing && existing.calls) {
          streamingParts.value = streamingParts.value.map(function (p) {
            return p.type === 'tools' ? { type: 'tools' as const, calls: (existing.calls || []).concat([call]) } : p
          })
        } else {
          streamingParts.value.push({ type: 'tools', calls: [call] })
        }
      } else if (currentEvent === 'done') {
        loading.value = true
        loadMessages().finally(function () { loading.value = false })
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
  streamingParts.value = []
  streamingContent.value = ''
  sending.value = false
  aborter = null
  scrollToBottom()
}

function stop() {
  aborter && aborter.abort()
  streaming.value = false
  streamingParts.value = []
}

onMounted(function () { loadMessages() })
onUnmounted(function () { aborter && aborter.abort() })
</script>

<template>
  <div class="agent-chat">
    <div ref="containerRef" class="agent-chat__log" @scroll="onScroll">
      <div v-if="hasMore" class="agent-chat__hint" :class="{ 'agent-chat__hint--loading': loading }">
        {{ loading ? '加载中...' : '↑ 向上滚动加载历史' }}
      </div>

      <div v-if="messages.length === 0 && !loading" class="agent-chat__empty">
        发送消息开始与 {{ props.agentName }} 对话
      </div>

      <template v-for="msg in messages" :key="msg.id || msg.created_at">
        <div class="msg-card" :class="'msg-card--' + msg.role">
          <div class="msg-card__header">
            <span class="msg-card__role">{{ msg.role === 'user' ? '你' : props.agentName }}</span>
            <span class="msg-card__time">{{ fmt(msg.created_at) }}</span>
          </div>

          <div class="msg-card__body">
            <template v-if="msg.parts && msg.parts.length > 0">
              <div v-for="(part, pi) in msg.parts" :key="pi" class="msg-step">

                <div v-if="part.type === 'input' && showInput" class="msg-step__input">
                  <div class="msg-step__label">📥 输入</div>
                  <div class="msg-step__text">{{ part.text }}</div>
                </div>

                <div v-if="part.type === 'thinking' && showThinking" class="msg-step__thinking">
                  <div class="msg-step__label" style="display: flex; justify-content: space-between; cursor: pointer"
                    @click="part._expanded = !part._expanded">
                    <span>💭 思考</span>
                    <span style="font-size: 11px; opacity: 0.5">{{ part._expanded ? '收起' : '展开' }}</span>
                  </div>
                  <div v-if="part._expanded || expandThinking" class="msg-step__text msg-step__text--mono">{{ part.text
                    }}</div>
                </div>

                <div v-if="part.type === 'tools' && showTools" class="msg-step__tools">
                  <div class="msg-step__label" style="display: flex; justify-content: space-between; cursor: pointer"
                    @click="part._expanded = !part._expanded">
                    <span>🔧 工具调用</span>
                    <span style="font-size: 11px; opacity: 0.5">{{ part._expanded ? '收起' : '展开' }}</span>
                  </div>
                  <div v-if="(part._expanded || expandTools) && part.calls">
                    <div v-for="(call, ci) in part.calls" :key="ci" class="msg-step__tool">
                      <div class="msg-step__tool-name">⚡ {{ call.name }}</div>
                      <pre class="msg-step__tool-args">{{ formatArgs(call.arguments) }}</pre>
                    </div>
                  </div>
                </div>

                <div v-if="part.type === 'answer'" class="msg-step__answer">
                  <div class="msg-step__label">💬 回答</div>
                  <div class="msg-step__text" style="white-space: pre-wrap">{{ part.text }}</div>
                </div>
              </div>
            </template>

            <div v-else class="msg-step__text" style="white-space: pre-wrap">{{ msg.content }}</div>
          </div>
        </div>
      </template>

      <div v-if="streaming && streamingParts.length > 0" class="msg-card msg-card--assistant msg-card--streaming">
        <div class="msg-card__body">
          <div v-for="(part, pi) in streamingParts" :key="'s_' + pi" class="msg-step">
            <div v-if="part.type === 'thinking'" class="msg-step__thinking">
              <div class="msg-step__label">💭 思考中...</div>
              <div class="msg-step__text msg-step__text--mono">{{ part.text }}</div>
            </div>
            <div v-if="part.type === 'answer'" class="msg-step__answer">
              <div class="msg-step__label">💬 回复中...</div>
              <div class="msg-step__text" style="white-space: pre-wrap">{{ part.text }}</div>
            </div>
            <div v-if="part.type === 'tools'" class="msg-step__tools">
              <div class="msg-step__label">🔧 工具调用</div>
              <div v-if="part.calls">
                <div v-for="(call, ci) in part.calls" :key="ci" class="msg-step__tool">
                  <div class="msg-step__tool-name">⚡ {{ call.name }}</div>
                  <pre class="msg-step__tool-args">{{ formatArgs(call.arguments) }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
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
  padding: 12px 16px;
}

.agent-chat__hint {
  text-align: center;
  padding: 8px;
  font-size: 11px;
  color: var(--color-text-muted);
}

.agent-chat__hint--loading {
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

.msg-card {
  margin-bottom: 16px;
  border-radius: 10px;
  border: 1px solid var(--color-border-primary);
  overflow: hidden;
}

.msg-card--user {
  background: var(--color-bg-secondary);
}

.msg-card--assistant {
  background: var(--color-bg-primary);
}

.msg-card--streaming {
  opacity: 0.85;
}

.msg-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 14px;
  background: var(--color-bg-tertiary);
  border-bottom: 1px solid var(--color-border-primary);
}

.msg-card__role {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
}

.msg-card__time {
  font-size: 10px;
  color: var(--color-text-muted);
}

.msg-card__body {
  padding: 0;
}

.msg-step {
  border-bottom: 1px solid var(--color-border-primary);
}

.msg-step:last-child {
  border-bottom: none;
}

.msg-step__label {
  padding: 6px 14px;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-secondary);
  background: var(--color-bg-input);
  user-select: none;
}

.msg-step__text {
  padding: 8px 14px;
  font-size: 13px;
  color: var(--color-text-primary);
  line-height: 1.6;
}

.msg-step__text--mono {
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}

.msg-step__input {}

.msg-step__thinking {}

.msg-step__tools {}

.msg-step__answer {}

.msg-step__tool {
  padding: 8px 14px;
  border-top: 1px solid var(--color-border-primary);
}

.msg-step__tool-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-accent-secondary);
  margin-bottom: 4px;
}

.msg-step__tool-args {
  background: var(--color-bg-input);
  padding: 8px;
  border-radius: 6px;
  font-size: 11px;
  color: var(--color-text-secondary);
  margin: 0;
  overflow-x: auto;
}
</style>
