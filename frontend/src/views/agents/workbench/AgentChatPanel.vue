<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, computed, watch } from 'vue'
import { getAuthToken } from '@/auth'
import { getApiBaseUrl } from '@/config'
import { http } from '@/api/http'
import type { ApiResponse } from '@/types/api'

interface StepCard {
  id: string
  role: 'user' | 'assistant'
  type: 'input' | 'thinking' | 'tools' | 'answer' | 'full_input'
  text?: string
  calls?: { name: string; arguments: string; result?: string; success?: boolean }[]
  time: string
  _expanded?: boolean
}

interface AgentMsg {
  id: string
  role: string
  content: string
  parts: Record<string, any>[]
  full_input?: string
  created_at: string
}

const props = withDefaults(defineProps<{
  agentId: string
  agentName: string
  displaySettings?: Record<string, boolean>
}>(), {
  displaySettings: function () { return {} as Record<string, boolean> },
})

const cards = ref<StepCard[]>([])
const loading = ref(false)
const hasMore = ref(true)
const streaming = ref(false)
const liveCards = ref<StepCard[]>([])
const input = ref('')
const sending = ref(false)
const containerRef = ref<HTMLElement | null>(null)
let aborter: AbortController | null = null

const rawMessages = ref<AgentMsg[]>([])

const showThinking = computed(function () { return !props.displaySettings || props.displaySettings.showThinking !== false })
const expandThinking = computed(function () { return !!props.displaySettings?.expandThinking })
const showTools = computed(function () { return !props.displaySettings || props.displaySettings.showTools !== false })
const expandTools = computed(function () { return !!props.displaySettings?.expandTools })
const showFullInput = computed(function () { return !!props.displaySettings?.showFullInput })
const expandFullInput = computed(function () { return !!props.displaySettings?.expandFullInput })
const autoCollapse = computed(function () { return !!props.displaySettings?.autoCollapse })
const showInput = computed(function () { return true })

const shouldAutoScroll = ref(true)

let cardCounter = 0
function nextCardId() { return '_c' + (++cardCounter) }

function initExpanded(card: StepCard) {
  if (card.type === 'thinking') {
    card._expanded = !autoCollapse.value || expandThinking.value
  } else if (card.type === 'tools') {
    card._expanded = !autoCollapse.value || expandTools.value
  } else if (card.type === 'full_input') {
    card._expanded = expandFullInput.value
  } else {
    card._expanded = true
  }
}

watch(expandThinking, function (v) {
  for (var i = 0; i < cards.value.length; i++) {
    if (cards.value[i].type === 'thinking') { cards.value[i]._expanded = v }
  }
  for (var j = 0; j < liveCards.value.length; j++) {
    if (liveCards.value[j].type === 'thinking') { liveCards.value[j]._expanded = v }
  }
})

watch(expandTools, function (v) {
  for (var i = 0; i < cards.value.length; i++) {
    if (cards.value[i].type === 'tools') { cards.value[i]._expanded = v }
  }
  for (var j = 0; j < liveCards.value.length; j++) {
    if (liveCards.value[j].type === 'tools') { liveCards.value[j]._expanded = v }
  }
})

watch(expandFullInput, function (v) {
  for (var i = 0; i < cards.value.length; i++) {
    if (cards.value[i].type === 'full_input') { cards.value[i]._expanded = v }
  }
})

watch(autoCollapse, function (v) {
  if (v) {
    for (var i = 0; i < cards.value.length; i++) {
      var c = cards.value[i]
      if (c.type === 'thinking' && !expandThinking.value) { c._expanded = false }
      if (c.type === 'tools' && !expandTools.value) { c._expanded = false }
      if (c.type === 'full_input' && !expandFullInput.value) { c._expanded = false }
    }
  }
})

watch(showThinking, function () { rebuildCardsFromRaw() })
watch(showTools, function () { rebuildCardsFromRaw() })
watch(showFullInput, function () { rebuildCardsFromRaw() })

function rebuildCardsFromRaw() {
  cards.value = messagesToCards(rawMessages.value)
  nextTick(function () { scrollToBottom() })
}

function messagesToCards(msgs: AgentMsg[]): StepCard[] {
  var result: StepCard[] = []
  for (var i = 0; i < msgs.length; i++) {
    var m = msgs[i]
    if (m.parts && m.parts.length > 0) {
      for (var j = 0; j < m.parts.length; j++) {
        var p = m.parts[j] as Record<string, any>
        if (p.type === 'input' && !showInput.value) continue
        if (p.type === 'thinking' && !showThinking.value) continue
        if ((p.type === 'tools' || p.type === 'tools_result') && !showTools.value) continue
        var card: StepCard = {
          id: m.id + '_' + j,
          role: m.role as 'user' | 'assistant',
          type: (p.type === 'tools_result' ? 'tools' : p.type) as StepCard['type'],
          text: p.text as string,
          calls: p.calls as any,
          time: m.created_at,
        }
        initExpanded(card)
        result.push(card)
      }
      if (m.role === 'assistant' && m.full_input && showFullInput.value) {
        var fiText = m.full_input
        try { fiText = JSON.stringify(JSON.parse(m.full_input), null, 2) } catch { /* keep raw */ }
        var fiCard: StepCard = {
          id: m.id + '_fi', role: 'assistant', type: 'full_input',
          text: fiText, time: m.created_at,
        }
        initExpanded(fiCard)
        console.log('assistant full_input', fiCard)
        result.push(fiCard)
      }
    } else if (m.content) {
      result.push({
        id: m.id + '_fallback', role: m.role as 'user' | 'assistant',
        type: 'answer', text: m.content, time: m.created_at,
      })
    }
  }
  return result
}

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
      rawMessages.value = newMsgs.concat(rawMessages.value)
      cards.value = messagesToCards(rawMessages.value)
      var oldH = containerRef.value ? containerRef.value.scrollHeight : 0
      nextTick(function () {
        if (containerRef.value) containerRef.value.scrollTop = containerRef.value.scrollHeight - oldH
      })
    } else {
      rawMessages.value = newMsgs
      cards.value = messagesToCards(rawMessages.value)
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
    var oldest = cards.value[0]
    if (oldest) loadMessages(oldest.id.split('_')[0])
  }
}

function scrollToBottom() {
  nextTick(function () {
    if (containerRef.value) containerRef.value.scrollTop = containerRef.value.scrollHeight
  })
}

function fmtTime(s: string) {
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
  liveCards.value = []

  var now = new Date().toISOString()
  cards.value.push({ id: nextCardId(), role: 'user', type: 'input', text: msg, time: now })
  nextTick(function () { scrollToBottom() })

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

    var liveThinking: StepCard | null = null
    var liveAnswer: StepCard | null = null

    function flushEvent() {
      var d = dataLines.join('\n').trim()
      dataLines.length = 0
      if (!d) { currentEvent = ''; return }
      var parsed: any
      try { parsed = JSON.parse(d) } catch { currentEvent = ''; return }

      if (currentEvent === 'reasoning') {
        if (!liveThinking) {
          liveThinking = { id: nextCardId(), role: 'assistant', type: 'thinking', text: '', time: new Date().toISOString() }
          liveThinking._expanded = autoCollapse.value ? expandThinking.value : true
        }
        liveThinking.text += (parsed.delta || '')
        rebuildLiveCards()
        if (shouldAutoScroll.value) scrollToBottom()
      } else if (currentEvent === 'thinking_done') {
        if (!liveThinking) {
          liveThinking = { id: nextCardId(), role: 'assistant', type: 'thinking', text: parsed.text || '', time: new Date().toISOString() }
        }
        liveThinking.text = parsed.text || liveThinking.text
        liveThinking._expanded = !autoCollapse.value || expandThinking.value
        rebuildLiveCards()
      } else if (currentEvent === 'delta') {
        if (!liveAnswer) {
          liveAnswer = { id: nextCardId(), role: 'assistant', type: 'answer', text: '', time: new Date().toISOString() }
        }
        liveAnswer.text += (parsed.delta || '')
        rebuildLiveCards()
        if (shouldAutoScroll.value) scrollToBottom()
      } else if (currentEvent === 'tool_call') {
        addToolCard(parsed)
      } else if (currentEvent === 'tool_result') {
        var tcCards = liveCards.value.filter(function (c) { return c.type === 'tools' })
        if (tcCards.length > 0) {
          var lastTc = tcCards[tcCards.length - 1]
          if (lastTc.calls && lastTc.calls.length > 0) {
            lastTc.calls[lastTc.calls.length - 1].result = parsed.result || ''
            lastTc.calls[lastTc.calls.length - 1].success = true
          }
        }
      } else if (currentEvent === 'done') {
        liveCards.value = []
        streaming.value = false
        loading.value = true
        loadMessages().finally(function () { loading.value = false })
      } else if (currentEvent === 'error') {
        liveCards.value.push({
          id: nextCardId(), role: 'assistant', type: 'answer',
          text: '错误: ' + (parsed.error || '未知'),
          time: new Date().toISOString(),
        })
      }
      currentEvent = ''
    }

    function rebuildLiveCards() {
      var result: StepCard[] = []
      if (liveThinking) result.push(liveThinking)
      for (var j = 0; j < liveCards.value.length; j++) {
        if (liveCards.value[j].type === 'tools') result.push(liveCards.value[j])
      }
      if (liveAnswer) result.push(liveAnswer)
      liveCards.value = result
    }

    function addToolCard(parsed: any) {
      var toolCard = liveCards.value.filter(function (c) { return c.type === 'tools' })[0]
      if (toolCard && toolCard.calls) {
        toolCard.calls.push({ name: parsed.tool || '', arguments: parsed.args || '' })
        toolCard._expanded = autoCollapse.value ? expandTools.value : true
      } else {
        var tc: StepCard = {
          id: nextCardId(), role: 'assistant', type: 'tools',
          calls: [{ name: parsed.tool || '', arguments: parsed.args || '' }],
          time: new Date().toISOString(),
        }
        tc._expanded = autoCollapse.value ? expandTools.value : true
        liveCards.value.push(tc)
      }
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
    if (e.name !== 'AbortError') {
      liveCards.value.push({
        id: nextCardId(), role: 'assistant', type: 'answer',
        text: '请求失败: ' + String(e), time: new Date().toISOString(),
      })
    }
  }

  streaming.value = false
  liveCards.value = []
  sending.value = false
  aborter = null
  scrollToBottom()
}

function stop() {
  if (aborter) aborter.abort()
  streaming.value = false
  liveCards.value = []
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

      <div v-if="cards.length === 0 && !loading" class="agent-chat__empty">
        发送消息开始与 {{ props.agentName }} 对话
      </div>

      <template v-for="card in cards" :key="card.id">
        <div v-if="card.role === 'user'" class="card-row card-row--user">
          <div class="step-card step-card--user">
            <div class="step-card__head">
              <span class="step-card__icon">👤</span><span>你</span>
              <span class="step-card__time">{{ fmtTime(card.time) }}</span>
            </div>
            <div class="step-card__body">{{ card.text }}</div>
          </div>
        </div>

        <div v-else class="card-row card-row--assistant">
          <!-- Thinking -->
          <div v-if="card.type === 'thinking' && showThinking" class="step-card step-card--thinking">
            <div class="step-card__head step-card__head--clickable" @click="card._expanded = !card._expanded">
              <span class="step-card__icon">💭</span><span class="step-card__label">{{ props.agentName }}</span>
              <span class="step-card__tag step-card__tag--thinking">思考</span>
              <span class="step-card__time">{{ fmtTime(card.time) }}</span>
              <span class="step-card__toggle">{{ card._expanded ? '▲' : '▼' }}</span>
            </div>
            <div v-if="card._expanded" class="step-card__body step-card__body--mono">{{ card.text }}</div>
          </div>

          <!-- Tools -->
          <div v-if="card.type === 'tools' && showTools" class="step-card step-card--tools">
            <div class="step-card__head step-card__head--clickable" @click="card._expanded = !card._expanded">
              <span class="step-card__icon">🔧</span><span class="step-card__label">{{ props.agentName }}</span>
              <span class="step-card__tag step-card__tag--tools">调用工具</span>
              <span v-if="card.calls" class="step-card__count">{{ card.calls.length }}</span>
              <span class="step-card__time">{{ fmtTime(card.time) }}</span>
              <span class="step-card__toggle">{{ card._expanded ? '▲' : '▼' }}</span>
            </div>
            <div v-if="card._expanded && card.calls" class="step-card__tool-list">
              <div v-for="(call, ci) in card.calls" :key="ci" class="step-card__tool">
                <div class="step-card__tool-head">
                  <span>⚡ {{ call.name }}</span>
                  <span v-if="call.result !== undefined" class="step-card__tool-ok"
                    :class="{ 'is-ok': call.success }">{{ call.success ? '✓' : '✗' }}</span>
                </div>
                <pre class="step-card__code">{{ fmtArgs(call.arguments) }}</pre>
                <div v-if="call.result !== undefined" class="step-card__tool-result">
                  <div class="step-card__result-label">结果</div>
                  <pre class="step-card__code step-card__code--result">{{ call.result }}</pre>
                </div>
              </div>
            </div>
          </div>

          <!-- Answer -->
          <div v-if="card.type === 'answer'" class="step-card step-card--answer">
            <div class="step-card__head">
              <span class="step-card__icon">🤖</span><span class="step-card__label">{{ props.agentName }}</span>
              <span class="step-card__time">{{ fmtTime(card.time) }}</span>
            </div>
            <div class="step-card__body" style="white-space: pre-wrap">{{ card.text }}</div>
          </div>

          <!-- Full input JSON -->
          <div v-if="card.type === 'full_input'" class="step-card step-card--full-input">
            <div class="step-card__head step-card__head--clickable" @click="card._expanded = !card._expanded">
              <span class="step-card__icon">📋</span><span class="step-card__label">{{ props.agentName }}</span>
              <span class="step-card__tag step-card__tag--input">完整输入</span>
              <span class="step-card__time">{{ fmtTime(card.time) }}</span>
              <span class="step-card__toggle">{{ card._expanded ? '▲' : '▼' }}</span>
            </div>
            <div v-if="card._expanded" class="step-card__body step-card__body--mono step-card__body--pre">{{ card.text
              }}</div>
          </div>
        </div>
      </template>

      <!-- Live streaming cards -->
      <template v-if="streaming && liveCards.length > 0">
        <div v-for="card in liveCards" :key="card.id" class="card-row card-row--assistant">
          <div v-if="card.type === 'thinking'" class="step-card step-card--thinking step-card--live">
            <div class="step-card__head">
              <span class="step-card__icon">💭</span><span class="step-card__label">{{ props.agentName }}</span>
              <span class="step-card__tag step-card__tag--thinking step-card__tag--pulse">思考中</span>
            </div>
            <div class="step-card__body step-card__body--mono">{{ card.text }}</div>
          </div>

          <div v-if="card.type === 'tools'" class="step-card step-card--tools step-card--live">
            <div class="step-card__head step-card__head--clickable" @click="card._expanded = !card._expanded">
              <span class="step-card__icon">🔧</span><span class="step-card__label">{{ props.agentName }}</span>
              <span class="step-card__tag step-card__tag--tools step-card__tag--pulse">调用工具</span>
              <span v-if="card.calls" class="step-card__count step-card__count--pulse">{{ card.calls.length }}</span>
              <span class="step-card__time">{{ fmtTime(card.time) }}</span>
              <span class="step-card__toggle">{{ card._expanded ? '▲' : '▼' }}</span>
            </div>
            <div v-if="card._expanded && card.calls" class="step-card__tool-list">
              <div v-for="(call, ci) in card.calls" :key="ci" class="step-card__tool">
                <div class="step-card__tool-head">
                  <span>⚡ {{ call.name }}</span>
                  <span v-if="call.result !== undefined" class="step-card__tool-ok is-ok">✓</span>
                </div>
                <pre class="step-card__code">{{ fmtArgs(call.arguments) }}</pre>
                <div v-if="call.result !== undefined" class="step-card__tool-result">
                  <pre class="step-card__code step-card__code--result">{{ call.result }}</pre>
                </div>
              </div>
            </div>
          </div>

          <div v-if="card.type === 'answer'" class="step-card step-card--answer step-card--live">
            <div class="step-card__head">
              <span class="step-card__icon">🤖</span><span class="step-card__label">{{ props.agentName }}</span>
              <span class="step-card__tag step-card__tag--pulse">回复中</span>
            </div>
            <div class="step-card__body" style="white-space: pre-wrap">{{ card.text }}</div>
          </div>

          <div v-if="card.type === 'full_input'" class="step-card step-card--full-input step-card--live">
            <div class="step-card__head step-card__head--clickable" @click="card._expanded = !card._expanded">
              <span class="step-card__icon">📋</span><span class="step-card__label">{{ props.agentName }}</span>
              <span class="step-card__tag step-card__tag--input">完整输入</span>
              <span class="step-card__time">{{ fmtTime(card.time) }}</span>
              <span class="step-card__toggle">{{ card._expanded ? '▲' : '▼' }}</span>
            </div>
            <div v-if="card._expanded" class="step-card__body step-card__body--mono step-card__body--pre">{{ card.text
              }}</div>
          </div>
        </div>
      </template>
    </div>

    <div class="agent-chat__input">
      <el-input v-model="input" type="textarea" :rows="2" placeholder="输入消息..." :disabled="sending" resize="none"
        @keydown.enter.exact.prevent="send()" />
      <div class="agent-chat__actions">
        <el-button v-if="streaming" circle type="danger" @click="stop" title="停止">⏹</el-button>
        <el-button circle type="primary" :loading="sending" :disabled="!input.trim()" @click="send()"
          title="发送">▶</el-button>
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
  padding: 20px 24px;
}

.agent-chat__hint {
  text-align: center;
  padding: 8px;
  font-size: 12px;
  color: var(--color-text-muted);
}

.agent-chat__hint--loading {
  color: var(--color-accent-primary);
}

.agent-chat__empty {
  text-align: center;
  padding: 80px 20px;
  color: var(--color-text-muted);
  font-size: 15px;
}

.agent-chat__input {
  padding: 12px 16px;
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

.card-row {
  display: flex;
  margin-bottom: 14px;
}

.card-row--user {
  justify-content: flex-end;
}

.card-row--assistant {
  justify-content: flex-start;
}

.step-card {
  max-width: 88%;
  min-width: 220px;
  border-radius: 10px;
  overflow: hidden;
}

.step-card--user {
  background: var(--color-accent-primary);
}

.step-card--thinking {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-primary);
  border-left: 3px solid #f59e0b;
}

.step-card--tools {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-primary);
  border-left: 3px solid #0071e3;
}

.step-card--answer {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-primary);
}

.step-card--full-input {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-primary);
  border-left: 3px solid rgba(255, 255, 255, 0.15);
}

.step-card--live {
  opacity: 0.92;
  border-left-style: dashed;
}

.step-card__head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 600;
  user-select: none;
}

.step-card--user .step-card__head {
  color: rgba(255, 255, 255, 0.95);
}

.step-card--thinking .step-card__head {
  color: var(--color-text-secondary);
  background: rgba(245, 158, 11, 0.06);
  border-bottom: 1px solid rgba(245, 158, 11, 0.12);
}

.step-card--tools .step-card__head {
  color: var(--color-text-secondary);
  background: rgba(0, 113, 227, 0.06);
  border-bottom: 1px solid rgba(0, 113, 227, 0.12);
}

.step-card--answer .step-card__head {
  color: var(--color-text-secondary);
  border-bottom: 1px solid var(--color-border-primary);
}

.step-card--full-input .step-card__head {
  color: var(--color-text-muted);
  border-bottom: 1px solid var(--color-border-primary);
}

.step-card__head--clickable {
  cursor: pointer;
}

.step-card__head--clickable:hover {
  opacity: 0.85;
}

.step-card__icon {
  font-size: 15px;
  flex-shrink: 0;
}

.step-card__label {
  flex-shrink: 0;
}

.step-card__time {
  margin-left: auto;
  font-size: 11px;
  font-weight: 400;
  opacity: 0.5;
  flex-shrink: 0;
}

.step-card__toggle {
  font-size: 10px;
  opacity: 0.4;
  flex-shrink: 0;
  cursor: pointer;
}

.step-card__tag {
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 6px;
  font-weight: 500;
}

.step-card__tag--thinking {
  background: rgba(245, 158, 11, 0.12);
  color: #f59e0b;
}

.step-card__tag--tools {
  background: rgba(0, 113, 227, 0.12);
  color: #60a5fa;
}

.step-card__tag--input {
  background: rgba(255, 255, 255, 0.06);
  color: var(--color-text-muted);
}

.step-card__tag--pulse {
  animation: pulse 1.5s infinite;
}

.step-card__count {
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 8px;
  background: rgba(0, 113, 227, 0.2);
  color: #60a5fa;
  font-weight: 600;
}

.step-card__count--pulse {
  animation: pulse 1.5s infinite;
}

@keyframes pulse {

  0%,
  100% {
    opacity: 1;
  }

  50% {
    opacity: 0.35;
  }
}

.step-card__body {
  padding: 10px 16px;
  font-size: 14px;
  color: var(--color-text-primary);
  line-height: 1.6;
  white-space: pre-wrap;
}

.step-card--user .step-card__body {
  color: rgba(255, 255, 255, 0.97);
}

.step-card__body--mono {
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 13px;
  color: var(--color-text-muted);
}

.step-card__body--pre {
  max-height: 500px;
  overflow-y: auto;
}

.step-card__tool-list {}

.step-card__tool {
  padding: 10px 14px;
  border-top: 1px solid var(--color-border-primary);
}

.step-card__tool-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-accent-secondary);
}

.step-card__tool-ok {
  font-size: 12px;
  color: var(--color-danger);
}

.step-card__tool-ok.is-ok {
  color: #22c55e;
}

.step-card__tool-result {
  margin-top: 8px;
}

.step-card__result-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-muted);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.step-card__code {
  background: rgba(0, 0, 0, 0.3);
  padding: 10px 12px;
  border-radius: 6px;
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 0;
  overflow-x: auto;
  font-family: 'Consolas', 'Courier New', monospace;
  line-height: 1.45;
}

.step-card__code--result {
  background: rgba(34, 197, 94, 0.04);
  border-left: 2px solid rgba(34, 197, 94, 0.25);
}
</style>
