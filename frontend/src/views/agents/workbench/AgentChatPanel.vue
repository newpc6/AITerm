<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue'
import { getAuthToken } from '@/auth'
import { getApiBaseUrl } from '@/config'
import { http } from '@/api/http'
import type { ApiResponse } from '@/types/api'

interface PartItem {
  type: 'input' | 'thinking' | 'tools' | 'tools_result' | 'answer'
  text?: string
  calls?: { name: string; arguments: string; result?: string; success?: boolean }[]
  _expanded?: boolean
}

interface AgentMsg {
  id: string
  role: string
  content: string
  parts: PartItem[]
  created_at: string
}

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
const input = ref('')
const sending = ref(false)
const containerRef = ref<HTMLElement | null>(null)
let aborter: AbortController | null = null

const showThinking = computed(function () { return !props.displaySettings || props.displaySettings.showThinking })
const showTools = computed(function () { return !props.displaySettings || props.displaySettings.showTools })
const showInput = computed(function () { return !props.displaySettings || props.displaySettings.showInput })
const shouldAutoScroll = ref(true)

async function loadMessages(beforeId?: string) {
  if (loading.value) return
  loading.value = true
  try {
    var params: Record<string, string> = { limit: '6' }
    if (beforeId) params.before_id = beforeId
    var resp = await http.get('/api/v1/agents/' + props.agentId + '/messages', { params: params })
    var body = resp.data as { data: { messages: AgentMsg[]; has_more: boolean } }
    var newMsgs = body.data.messages || []
    var more = body.data.has_more

    if (beforeId) {
      var oldH = containerRef.value ? containerRef.value.scrollHeight : 0
      messages.value = newMsgs.concat(messages.value)
      nextTick(function () {
        if (containerRef.value) containerRef.value.scrollTop = containerRef.value.scrollHeight - oldH
      })
    } else {
      messages.value = newMsgs
      nextTick(function () { scrollToBottom() })
    }
    hasMore.value = more
  } catch { /* */ }
  finally { loading.value = false }
}

function onScroll() {
  var el = containerRef.value
  if (!el) return
  shouldAutoScroll.value = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  if (el.scrollTop < 60 && hasMore.value && !loading.value) {
    var oldest = messages.value[0]
    if (oldest) loadMessages(oldest.id)
  }
}

function scrollToBottom() {
  nextTick(function () {
    if (containerRef.value) containerRef.value.scrollTop = containerRef.value.scrollHeight
  })
}

function fmt(s: string) {
  if (!s) return ''
  try { return new Date(s).toLocaleTimeString() } catch { return '' }
}

function fmtArgs(args: string): string {
  try { return JSON.stringify(JSON.parse(args), null, 2) } catch { return args }
}

async function send() {
  var msg = input.value.trim()
  if (!msg || sending.value || streaming.value) return
  input.value = ''
  sending.value = true
  streaming.value = true
  streamingParts.value = []

  var now = new Date().toISOString()
  messages.value.push({ id: '', role: 'user', content: msg, parts: [{ type: 'input', text: msg }], created_at: now })
  nextTick(function () { scrollToBottom() })

  var assistMsg: AgentMsg = { id: now + '_a', role: 'assistant', content: '', parts: [], created_at: now }
  messages.value.push(assistMsg)

  aborter = new AbortController()

  try {
    var token = getAuthToken() || ''
    var baseUrl = getApiBaseUrl()
    var url = baseUrl + '/api/v1/agents/' + props.agentId + '/chat'
    var headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = 'Bearer ' + token

    var resp = await fetch(url, {
      method: 'POST', signal: aborter.signal, headers,
      body: JSON.stringify({ message: msg }),
    })

    if (!resp.ok || !resp.body) throw new Error('HTTP ' + resp.status)

    var reader = resp.body.getReader()
    var decoder = new TextDecoder()
    var buffer = ''
    var currentEvent = ''
    var dataLines: string[] = []
    var thinkingText = ''
    var answerText = ''
    var liveTools: PartItem[] = []

    function flushEvent() {
      var d = dataLines.join('\n').trim()
      dataLines.length = 0
      if (!d) { currentEvent = ''; return }
      var parsed: any
      try { parsed = JSON.parse(d) } catch { currentEvent = ''; return }

      if (currentEvent === 'reasoning') {
        thinkingText += (parsed.delta || '')
        var thinkingParts: PartItem[] = [{ type: 'thinking', text: thinkingText, _expanded: true }]
        streamingParts.value = thinkingParts.concat(liveTools)
        if (answerText) streamingParts.value.push({ type: 'answer', text: answerText })
        if (shouldAutoScroll.value) scrollToBottom()
      } else if (currentEvent === 'thinking_done') {
        var thinkingParts2: PartItem[] = [{ type: 'thinking', text: parsed.text || thinkingText, _expanded: false }]
        streamingParts.value = thinkingParts2.concat(liveTools)
        if (answerText) streamingParts.value.push({ type: 'answer', text: answerText })
      } else if (currentEvent === 'delta') {
        answerText += (parsed.delta || '')
        var newParts: PartItem[] = []
        if (thinkingText) newParts.push({ type: 'thinking', text: thinkingText, _expanded: false })
        newParts = newParts.concat(liveTools)
        if (answerText) newParts.push({ type: 'answer', text: answerText })
        streamingParts.value = newParts
        assistMsg.content = answerText
        if (shouldAutoScroll.value) scrollToBottom()
      } else if (currentEvent === 'tool_call') {
        var call = { name: parsed.tool || '', arguments: parsed.args || '' }
        var existing = liveTools.filter(function (p) { return p.type === 'tools' })[0]
        if (existing && existing.calls) {
          existing.calls.push(call)
        } else {
          liveTools.push({ type: 'tools', calls: [call], _expanded: true })
        }
        var toolParts: PartItem[] = []
        if (thinkingText) toolParts.push({ type: 'thinking', text: thinkingText, _expanded: false })
        toolParts = toolParts.concat(liveTools)
        if (answerText) toolParts.push({ type: 'answer', text: answerText })
        streamingParts.value = toolParts
      } else if (currentEvent === 'tool_result') {
        var lastTool = liveTools.filter(function (p) { return p.type === 'tools' })[0]
        if (lastTool && lastTool.calls && lastTool.calls.length > 0) {
          var lastCall = lastTool.calls[lastTool.calls.length - 1]
          lastCall.result = parsed.result || ''
          lastCall.success = true
        }
        var resParts: PartItem[] = []
        if (thinkingText) resParts.push({ type: 'thinking', text: thinkingText, _expanded: false })
        resParts = resParts.concat(liveTools)
        if (answerText) resParts.push({ type: 'answer', text: answerText })
        streamingParts.value = resParts
      } else if (currentEvent === 'done') {
        loading.value = true
        loadMessages().finally(function () { loading.value = false })
      } else if (currentEvent === 'error') {
        assistMsg.content = '\u9519\u8bef: ' + (parsed.error || '\u672a\u77e5\u9519\u8bef')
      }
      currentEvent = ''
    }

    while (true) {
      var result = await reader.read()
      buffer += decoder.decode(result.value || new Uint8Array(), { stream: !result.done })

      var idx = buffer.indexOf('\n')
      while (idx >= 0) {
        var line = buffer.slice(0, idx).replace(/\r$/, '')
        buffer = buffer.slice(idx + 1)
        if (!line.trim()) { flushEvent() }
        else if (line.startsWith('event:')) { currentEvent = line.slice(6).trim() }
        else if (line.startsWith('data:')) { dataLines.push(line.slice(5).trim()) }
        idx = buffer.indexOf('\n')
      }

      if (result.done) {
        if (buffer.trim() && buffer.trim().startsWith('data:')) dataLines.push(buffer.trim().slice(5).trim())
        flushEvent()
        break
      }
    }
  } catch (e: any) {
    if (e.name !== 'AbortError') assistMsg.content = '\u8bf7\u6c42\u5931\u8d25: ' + String(e)
  }

  streaming.value = false
  streamingParts.value = []
  sending.value = false
  aborter = null
  scrollToBottom()
}

function stop() {
  if (aborter) aborter.abort()
  streaming.value = false
  streamingParts.value = []
}

onMounted(function () { loadMessages() })
onUnmounted(function () { if (aborter) aborter.abort() })
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
        <div class="msg-wrapper" :class="'msg-wrapper--' + msg.role">
          <div class="msg-card" :class="'msg-card--' + msg.role">
            <div class="msg-card__role">
              <span class="msg-card__role-icon">{{ msg.role === 'user' ? '👤' : '🤖' }}</span>
              <span>{{ msg.role === 'user' ? '你' : props.agentName }}</span>
              <span class="msg-card__time">{{ fmt(msg.created_at) }}</span>
            </div>

            <div v-if="msg.parts && msg.parts.length > 0" class="msg-card__steps">
              <div v-for="(part, pi) in msg.parts" :key="pi">
                <!-- Input step -->
                <div v-if="part.type === 'input' && showInput" class="step step--input">
                  <div class="step__label">
                    <span class="step__icon">📥</span> 输入
                  </div>
                  <div class="step__body">{{ part.text }}</div>
                </div>

                <!-- Thinking step -->
                <div v-if="part.type === 'thinking' && showThinking" class="step step--thinking">
                  <div class="step__label step__label--clickable" @click="part._expanded = !part._expanded">
                    <span class="step__icon">💭</span> 思考
                    <span class="step__toggle">{{ (part._expanded !== false) ? '收起 ▲' : '展开 ▼' }}</span>
                  </div>
                  <div v-if="part._expanded !== false" class="step__body step__body--mono">{{ part.text }}</div>
                </div>

                <!-- Tools step -->
                <div v-if="part.type === 'tools' && showTools" class="step step--tools">
                  <div class="step__label step__label--clickable" @click="part._expanded = !part._expanded">
                    <span class="step__icon">🔧</span> 工具调用
                    <span v-if="part.calls" class="step__badge">{{ part.calls.length }}</span>
                    <span class="step__toggle">{{ (part._expanded !== false) ? '收起 ▲' : '展开 ▼' }}</span>
                  </div>
                  <div v-if="part._expanded !== false && part.calls" class="step__tool-list">
                    <div v-for="(call, ci) in part.calls" :key="ci" class="step__tool-item">
                      <div class="step__tool-header">
                        <span class="step__tool-name">⚡ {{ call.name }}</span>
                        <span v-if="call.result" class="step__tool-status"
                          :class="{ 'step__tool-status--ok': call.success }">
                          {{ call.success ? '✓' : '✗' }}
                        </span>
                      </div>
                      <pre class="step__code">{{ fmtArgs(call.arguments) }}</pre>
                      <div v-if="call.result" class="step__tool-result">
                        <div class="step__tool-result-label">结果:</div>
                        <pre class="step__code step__code--result">{{ call.result }}</pre>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Tools result step (from persisted data) -->
                <div v-if="part.type === 'tools_result' && showTools" class="step step--tools-result">
                  <div class="step__label step__label--clickable" @click="part._expanded = !part._expanded">
                    <span class="step__icon">✅</span> 工具执行结果
                    <span v-if="part.calls" class="step__badge">{{ part.calls.length }}</span>
                    <span class="step__toggle">{{ (part._expanded !== false) ? '收起 ▲' : '展开 ▼' }}</span>
                  </div>
                  <div v-if="part._expanded !== false && part.calls" class="step__tool-list">
                    <div v-for="(call, ci) in part.calls" :key="ci" class="step__tool-item">
                      <div class="step__tool-header">
                        <span class="step__tool-name">⚡ {{ call.name }}</span>
                        <span class="step__tool-status" :class="{ 'step__tool-status--ok': call.success }">
                          {{ call.success ? '✓ 成功' : '✗ 失败' }}
                        </span>
                      </div>
                      <pre class="step__code">{{ fmtArgs(call.arguments) }}</pre>
                      <div v-if="call.result" class="step__tool-result">
                        <div class="step__tool-result-label">结果:</div>
                        <pre class="step__code step__code--result">{{ call.result }}</pre>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Answer step -->
                <div v-if="part.type === 'answer'" class="step step--answer">
                  <div class="step__label">
                    <span class="step__icon">💬</span> 回答
                  </div>
                  <div class="step__body" style="white-space: pre-wrap">{{ part.text }}</div>
                </div>
              </div>
            </div>
            <div v-else class="msg-card__fallback">{{ msg.content }}</div>
          </div>
        </div>
      </template>

      <!-- Streaming assistant card -->
      <div v-if="streaming && streamingParts.length > 0" class="msg-wrapper msg-wrapper--assistant">
        <div class="msg-card msg-card--assistant msg-card--streaming">
          <div class="msg-card__role">
            <span class="msg-card__role-icon">🤖</span>
            <span>{{ props.agentName }}</span>
            <span class="msg-card__pulse"></span>
          </div>
          <div class="msg-card__steps">
            <div v-for="(part, pi) in streamingParts" :key="'s_' + pi">
              <div v-if="part.type === 'thinking'" class="step step--thinking step--live">
                <div class="step__label">
                  <span class="step__icon">💭</span> 思考中...
                </div>
                <div class="step__body step__body--mono">{{ part.text }}</div>
              </div>
              <div v-if="part.type === 'tools'" class="step step--tools step--live">
                <div class="step__label">
                  <span class="step__icon">🔧</span> 调用工具
                  <span v-if="part.calls" class="step__badge step__badge--live">{{ part.calls.length }}</span>
                </div>
                <div v-if="part.calls" class="step__tool-list">
                  <div v-for="(call, ci) in part.calls" :key="ci" class="step__tool-item">
                    <div class="step__tool-header">
                      <span class="step__tool-name">⚡ {{ call.name }}</span>
                      <span v-if="call.result" class="step__tool-status step__tool-status--ok">✓</span>
                    </div>
                    <pre class="step__code">{{ fmtArgs(call.arguments) }}</pre>
                    <div v-if="call.result" class="step__tool-result">
                      <pre class="step__code step__code--result">{{ call.result }}</pre>
                    </div>
                  </div>
                </div>
              </div>
              <div v-if="part.type === 'answer'" class="step step--answer step--live">
                <div class="step__label">
                  <span class="step__icon">💬</span> 回复中...
                </div>
                <div class="step__body" style="white-space: pre-wrap">{{ part.text }}</div>
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
  padding: 16px 20px;
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
  padding: 60px 20px;
  color: var(--color-text-muted);
  font-size: 13px;
}

.agent-chat__input {
  padding: 10px 16px;
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

/* Message alignment */
.msg-wrapper {
  display: flex;
  margin-bottom: 20px;
}

.msg-wrapper--user {
  justify-content: flex-end;
}

.msg-wrapper--assistant {
  justify-content: flex-start;
}

.msg-card {
  max-width: 85%;
  min-width: 200px;
  border-radius: 10px;
  overflow: hidden;
}

.msg-card--user {
  background: var(--color-accent-primary);
}

.msg-card--assistant {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-primary);
}

.msg-card--streaming {
  border-color: rgba(0, 113, 227, 0.3);
}

.msg-card__role {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  font-size: 12px;
  font-weight: 600;
}

.msg-card--user .msg-card__role {
  color: rgba(255, 255, 255, 0.9);
}

.msg-card--assistant .msg-card__role {
  color: var(--color-text-secondary);
  border-bottom: 1px solid var(--color-border-primary);
}

.msg-card__role-icon {
  font-size: 14px;
}

.msg-card__time {
  margin-left: auto;
  font-size: 10px;
  font-weight: 400;
  opacity: 0.6;
}

.msg-card__pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-accent-primary);
  animation: pulse 1s infinite;
  margin-left: auto;
}

@keyframes pulse {

  0%,
  100% {
    opacity: 1;
  }

  50% {
    opacity: 0.3;
  }
}

.msg-card__steps {}

.msg-card__fallback {
  padding: 10px 14px;
  font-size: 13px;
  white-space: pre-wrap;
  color: var(--color-text-primary);
}

.msg-card--user .msg-card__fallback {
  color: rgba(255, 255, 255, 0.95);
}

/* Steps */
.step {
  border-top: 1px solid var(--color-border-primary);
}

.step:first-child {
  border-top: none;
}

.step__label {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  font-size: 11px;
  font-weight: 600;
  user-select: none;
}

.step--input .step__label {
  background: rgba(34, 197, 94, 0.08);
  color: #4ade80;
}

.step--thinking .step__label {
  background: rgba(245, 158, 11, 0.08);
  color: #fbbf24;
}

.step--tools .step__label {
  background: rgba(0, 113, 227, 0.08);
  color: #60a5fa;
}

.step--tools-result .step__label {
  background: rgba(34, 197, 94, 0.08);
  color: #4ade80;
}

.step--answer .step__label {
  background: rgba(255, 255, 255, 0.03);
  color: var(--color-text-secondary);
}

.step--live .step__label {
  opacity: 0.85;
}

.step__label--clickable {
  cursor: pointer;
}

.step__label--clickable:hover {
  opacity: 0.85;
}

.step__toggle {
  margin-left: auto;
  font-size: 10px;
  opacity: 0.5;
  font-weight: 400;
}

.step__badge {
  margin-left: auto;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 8px;
  background: rgba(0, 113, 227, 0.2);
  color: #60a5fa;
}

.step__badge--live {
  animation: pulse 1s infinite;
}

.step__body {
  padding: 8px 14px;
  font-size: 13px;
  color: var(--color-text-primary);
  line-height: 1.6;
}

.step__body--mono {
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--color-text-muted);
}

.step__tool-list {}

.step__tool-item {
  padding: 10px 14px;
  border-top: 1px solid var(--color-border-primary);
}

.step__tool-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.step__tool-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-accent-secondary);
}

.step__tool-status {
  font-size: 11px;
  color: var(--color-danger);
}

.step__tool-status--ok {
  color: #4ade80;
}

.step__code {
  background: rgba(0, 0, 0, 0.3);
  padding: 8px 10px;
  border-radius: 6px;
  font-size: 11px;
  color: var(--color-text-secondary);
  margin: 0;
  overflow-x: auto;
  font-family: 'Consolas', 'Courier New', monospace;
  line-height: 1.4;
}

.step__code--result {
  background: rgba(34, 197, 94, 0.06);
  border-left: 2px solid rgba(34, 197, 94, 0.3);
}

.step__tool-result {
  margin-top: 8px;
}

.step__tool-result-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--color-text-muted);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
</style>
