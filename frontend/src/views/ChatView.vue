<template>
  <div class="chat-page">
    <!-- 左侧: 历史会话 -->
    <div class="sessions panel-card">
      <div class="sessions-header">
        <span>历史会话</span>
        <el-tooltip content="新建会话" placement="bottom">
          <el-icon class="new-btn" @click="newConversation"><Plus /></el-icon>
        </el-tooltip>
      </div>
      <div class="session-list">
        <div
          v-for="c in conversations"
          :key="c.id"
          class="session-item"
          :class="{ active: c.id === conversationId }"
          @click="switchConversation(c.id)"
        >
          <el-icon class="session-icon"><ChatLineSquare /></el-icon>
          <div class="session-info">
            <div class="session-title">{{ c.title }}</div>
            <div class="session-meta">{{ formatTime(c.lastMessageAt) }} · {{ c.messageCount }} 条</div>
          </div>
        </div>
        <el-empty v-if="!conversations.length" description="暂无历史会话" :image-size="60" />
      </div>
    </div>

    <!-- 中间: 聊天区域 -->
    <div class="chat-main panel-card">
      <div class="chat-toolbar">
        <div class="kb-select">
          <span class="kb-label">知识库:</span>
          <el-select
            v-model="knowledgeBaseId"
            placeholder="选择知识库"
            size="default"
            style="width: 220px"
          >
            <el-option
              v-for="kb in kbList"
              :key="kb.id"
              :label="kb.name"
              :value="kb.id"
            >
              <span>{{ kb.name }}</span>
              <span class="kb-option-meta">{{ kb.chunkCount }} chunks</span>
            </el-option>
          </el-select>
        </div>
        <div class="toolbar-actions">
          <el-button size="small" :disabled="!conversationId || asking" @click="onRegenerate">
            <el-icon><RefreshRight /></el-icon>&nbsp;重新生成
          </el-button>
          <el-popconfirm title="确认清空当前会话消息?" @confirm="onClear">
            <template #reference>
              <el-button size="small" :disabled="!conversationId" type="danger" plain>
                <el-icon><Delete /></el-icon>&nbsp;清空对话
              </el-button>
            </template>
          </el-popconfirm>
        </div>
      </div>

      <div ref="scrollRef" class="chat-body">
        <div v-if="!messages.length" class="empty-state">
          <el-icon :size="52" color="#d97757"><ChatDotRound /></el-icon>
          <h3>你好, 想了解什么网络安全知识?</h3>
          <p>回答基于知识库真实检索结果, 并附带引用来源</p>
          <div class="quick-questions">
            <el-button
              v-for="q in quickQuestions"
              :key="q"
              size="small"
              round
              @click="askQuick(q)"
            >{{ q }}</el-button>
          </div>
        </div>

        <div v-for="msg in messages" :key="msg.id" class="msg-row" :class="msg.role">
          <div class="avatar">
            <el-icon v-if="msg.role === 'user'" :size="18"><User /></el-icon>
            <el-icon v-else :size="20" color="#d97757"><Shield /></el-icon>
          </div>
          <div class="bubble">
            <MarkdownView class="chat-text" :source="msg.content" />
            <SourceList v-if="msg.role === 'assistant' && msg.sources?.length" :sources="msg.sources" />
            <div v-if="msg.role === 'assistant' && confOf(msg.id)" class="conf-row">
              <el-tag size="small" :type="confTagType(confOf(msg.id)!.level)" effect="plain">
                证据置信度: {{ confOf(msg.id)!.label }}
                ({{ (confOf(msg.id)!.retrievalConfidence * 100).toFixed(1) }}%)
              </el-tag>
            </div>
            <div v-if="msg.role === 'assistant'" class="msg-footer">
              <span class="meta">检索 {{ msg.retrievalTime }}ms · 生成 {{ msg.generationTime }}ms</span>
              <span v-if="msg.trace?.llmTtftMs" class="meta">首字 {{ msg.trace.llmTtftMs }}ms</span>
              <span v-if="msg.totalTokens" class="meta">{{ msg.totalTokens }} tokens</span>
            </div>
            <RagTracePanel
              v-if="msg.role === 'assistant' && msg.trace"
              :trace="msg.trace"
              :analysis="extras[msg.id]?.analysis"
              :default-open="userStore.isAdmin"
            />
          </div>
        </div>

        <div v-if="asking" class="msg-row assistant">
          <div class="avatar"><el-icon :size="20" color="#d97757"><Shield /></el-icon></div>
          <div class="bubble">
            <!-- 阶段提示: 正在检索 → 正在组织证据 → 正在生成 -->
            <div v-if="!streamContent" class="typing">
              <span></span><span></span><span></span>
              <em>{{ stageText }}</em>
            </div>
            <template v-else>
              <div class="stage-caption">{{ stageText }}</div>
              <MarkdownView class="chat-text streaming" :source="streamContent" />
              <span class="stream-cursor"></span>
            </template>
          </div>
        </div>
      </div>

      <div class="chat-input">
        <el-input
          v-model="question"
          type="textarea"
          :rows="3"
          resize="none"
          placeholder="输入网络安全问题, 如: Spring Boot 如何防止 SQL 注入? (Enter 发送, Shift+Enter 换行)"
          :disabled="asking"
          @keydown.enter.exact.prevent="onAsk"
        />
        <div class="input-footer">
          <div class="params">
            <span class="param-label">Top-K</span>
            <el-input-number v-model="topK" :min="1" :max="20" size="small" style="width: 90px" />
            <span class="param-label">Temperature</span>
            <el-input-number v-model="temperature" :min="0" :max="1" :step="0.1" size="small" style="width: 100px" />
          </div>
          <!-- 流式进行中: 发送按钮切换为停止(abort 当次 fetch, 已生成部分保留) -->
          <el-button
            v-if="asking"
            type="danger"
            plain
            class="send-btn"
            @click="stopStreaming"
          >
            <el-icon><VideoPause /></el-icon>&nbsp;停 止
          </el-button>
          <el-button
            v-else
            type="primary"
            class="send-btn"
            :disabled="!question.trim() || !knowledgeBaseId"
            @click="onAsk"
          >
            <el-icon><Promotion /></el-icon>&nbsp;发 送
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import MarkdownView from '@/components/MarkdownView.vue'
import SourceList from '@/components/SourceList.vue'
import RagTracePanel from '@/components/RagTracePanel.vue'
import {
  askStream, regenerate, listMessages, clearMessages, pageConversations,
  type MessageItem, type ConversationItem, type QueryAnalysis, type EvidenceConfidence,
} from '@/api/chat'
import { listEnabledKb, type KnowledgeBase } from '@/api/kb'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const conversations = ref<ConversationItem[]>([])
const conversationId = ref<number | null>(null)
const messages = ref<MessageItem[]>([])
/** 当前会话消息的附加数据(置信度/分析), done 事件携带, 不入库 */
const extras = ref<Record<number, { analysis?: QueryAnalysis | null; confidence?: EvidenceConfidence | null }>>({})
const kbList = ref<KnowledgeBase[]>([])
const knowledgeBaseId = ref<number | null>(null)
const question = ref('')
const asking = ref(false)
const topK = ref(5)
const temperature = ref(0.3)
const scrollRef = ref<HTMLDivElement>()

/** 流式状态: 阶段提示 + 已生成的增量文本 */
type StreamStage = 'retrieving' | 'evidencing' | 'generating'
const streamStage = ref<StreamStage>('retrieving')
const streamContent = ref('')
const STAGE_TEXT: Record<StreamStage, string> = {
  retrieving: '正在检索知识库…',
  evidencing: '正在组织证据…',
  generating: '正在生成回答…',
}
const stageText = computed(() => STAGE_TEXT[streamStage.value])

/** 流式中止控制: 停止按钮/会话切换/清空对话共用 */
let abortController: AbortController | null = null
/** 生成序号: 中断时 +1, 使旧流的迟到事件(含已入列的 partial)失效 */
let genSeq = 0

function stopStreaming() {
  // 仅 abort, 不 +genSeq: 保留 partial 到当前视图(与切换会话的丢弃语义区分)
  abortController?.abort()
}

/** 切换/新建/清空会话时中断进行中的流(旧流事件不再写入新视图) */
function interruptStreaming() {
  if (abortController) {
    genSeq++
    abortController.abort()
  }
}

function confTagType(level: string): 'success' | 'warning' | 'danger' {
  if (level === 'sufficient') return 'success'
  if (level === 'moderate') return 'warning'
  return 'danger'
}

/** 消息的证据置信度(不存在返回 null, 模板判空) */
function confOf(id: number): EvidenceConfidence | null {
  return extras.value[id]?.confidence ?? null
}

const quickQuestions = [
  'SQL 注入的攻击原理是什么?',
  '如何防御 XSS 跨站脚本攻击?',
  'Spring Boot 如何防止 SQL 注入?',
  'JWT 有哪些常见安全风险?',
  '什么是 OWASP API 安全的 BOLA?',
]

function formatTime(t: string | null) {
  if (!t) return '-'
  return t.replace('T', ' ').slice(5, 16)
}

async function loadConversations() {
  const res = await pageConversations({ page: 1, size: 50 })
  conversations.value = res.records
}

function newConversation() {
  interruptStreaming()
  conversationId.value = null
  messages.value = []
}

async function switchConversation(id: number) {
  interruptStreaming()
  conversationId.value = id
  messages.value = await listMessages(id)
  const conv = conversations.value.find((c) => c.id === id)
  if (conv?.knowledgeBaseId) knowledgeBaseId.value = conv.knowledgeBaseId
  scrollToBottom()
}

async function onAsk() {
  const q = question.value.trim()
  if (!q || asking.value || !knowledgeBaseId.value) return
  asking.value = true
  streamStage.value = 'retrieving'
  streamContent.value = ''
  // 立即渲染用户消息
  messages.value.push({
    id: -Date.now(),
    conversationId: conversationId.value ?? 0,
    role: 'user',
    content: q,
    sources: null,
    trace: null,
    retrievalTime: 0,
    generationTime: 0,
    totalTokens: 0,
    createdAt: new Date().toISOString(),
  })
  question.value = ''
  scrollToBottom()

  let firstDelta = true
  // 本轮流的中止控制器: 停止按钮/切换会话/清空对话时 abort(askStream 对 AbortError 静默)
  const controller = new AbortController()
  abortController = controller
  const myGen = genSeq // 快照: interruptStreaming 会 +genSeq 使旧流事件失效

  await askStream(
    {
      question: q,
      conversationId: conversationId.value,
      knowledgeBaseId: knowledgeBaseId.value,
      topK: topK.value,
      temperature: temperature.value,
    },
    {
      onStart: (e) => {
        if (myGen !== genSeq) return
        conversationId.value = e.conversationId
        // 用户消息的临时负数 ID 替换为真实 ID
        const userMsg = messages.value[messages.value.length - 1]
        if (userMsg?.role === 'user' && userMsg.id < 0) userMsg.id = e.userMessageId
      },
      onRetrieval: () => {
        if (myGen !== genSeq) return
        streamStage.value = 'evidencing'
      },
      onDelta: (text) => {
        if (myGen !== genSeq) return
        if (firstDelta) {
          firstDelta = false
          streamStage.value = 'generating'
        }
        streamContent.value += text
        scrollToBottom()
      },
      onDone: (e) => {
        if (myGen !== genSeq) return
        const r = e.response
        messages.value.push({
          id: e.assistantMessageId,
          conversationId: conversationId.value ?? 0,
          role: 'assistant',
          content: r.answer,
          sources: r.sources,
          trace: r.trace,
          retrievalTime: r.retrievalTime,
          generationTime: r.generationTime,
          totalTokens: r.totalTokens,
          createdAt: new Date().toISOString(),
        })
        if (e.assistantMessageId) {
          extras.value[e.assistantMessageId] = {
            analysis: r.analysis,
            confidence: r.confidence,
          }
        }
        loadConversations()
      },
      onError: (msg) => {
        ElMessage.error(msg)
      },
    },
    { signal: controller.signal },
  )

  abortController = null

  // 会话已被切换/新建/清空: 不向新视图写入残留, 直接收尾
  if (myGen !== genSeq) {
    asking.value = false
    streamContent.value = ''
    return
  }

  // 手动停止: 已生成的部分保留为一条本地消息(服务端 done 未到达不落库, 刷新后消失)
  if (controller.signal.aborted && streamContent.value.trim()) {
    messages.value.push({
      id: -Date.now(),
      conversationId: conversationId.value ?? 0,
      role: 'assistant',
      content: streamContent.value + '\n\n> ⏹ 已手动停止生成',
      sources: null,
      trace: null,
      retrievalTime: 0,
      generationTime: 0,
      totalTokens: 0,
      createdAt: new Date().toISOString(),
    })
    loadConversations()
  }

  // 流结束: 清空流式展示区(成功时完整消息已入列, 失败时保留用户消息)
  asking.value = false
  streamContent.value = ''
  scrollToBottom()
}

function askQuick(q: string) {
  question.value = q
  onAsk()
}

async function onRegenerate() {
  if (!conversationId.value || asking.value) return
  asking.value = true
  try {
    await regenerate(conversationId.value)
    // 重新拉取完整消息(包含重新生成的回答)
    messages.value = await listMessages(conversationId.value)
    scrollToBottom()
  } catch {
    /* 错误已由拦截器提示 */
  } finally {
    asking.value = false
  }
}

async function onClear() {
  if (!conversationId.value) return
  interruptStreaming()
  await clearMessages(conversationId.value)
  messages.value = []
  loadConversations()
  ElMessage.success('会话已清空')
}

function scrollToBottom() {
  nextTick(() => {
    if (scrollRef.value) scrollRef.value.scrollTop = scrollRef.value.scrollHeight
  })
}

onMounted(async () => {
  kbList.value = await listEnabledKb()
  if (kbList.value.length) knowledgeBaseId.value = kbList.value[0].id
  await loadConversations()
})
</script>

<style scoped>
.chat-page {
  display: flex;
  gap: 14px;
  height: 100%;
  padding: 14px;
}
.sessions {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.sessions-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 14px 10px;
  font-weight: 600;
  font-size: 14px;
}
.new-btn {
  cursor: pointer;
  color: var(--accent);
  font-size: 18px;
}
.new-btn:hover {
  transform: scale(1.15);
}
.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 8px;
}
.session-item {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 10px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  border: 1px solid transparent;
}
.session-item:hover {
  background: var(--bg-hover);
}
.session-item.active {
  background: var(--accent-soft);
  border-color: rgba(217, 119, 87, 0.35);
}
.session-icon {
  color: var(--text-secondary);
  flex-shrink: 0;
}
.session-info {
  min-width: 0;
}
.session-title {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.session-meta {
  font-size: 11.5px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.chat-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-color);
  flex-wrap: wrap;
  gap: 8px;
}
.kb-select {
  display: flex;
  align-items: center;
  gap: 8px;
}
.kb-label {
  color: var(--text-secondary);
  font-size: 13px;
}
.kb-option-meta {
  float: right;
  color: var(--text-secondary);
  font-size: 12px;
  margin-left: 12px;
}
.toolbar-actions {
  display: flex;
  gap: 8px;
}

.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}
.empty-state {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.empty-state h3 {
  margin: 10px 0 0;
  font-family: var(--font-serif);
  font-size: 24px;
  font-weight: 600;
}
.empty-state p {
  color: var(--text-secondary);
  font-size: 13px;
  margin: 0 0 14px;
}
.quick-questions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  max-width: 640px;
  justify-content: center;
}

.msg-row {
  display: flex;
  gap: 12px;
  margin-bottom: 22px;
}
.msg-row.user {
  flex-direction: row-reverse;
}
.avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--text-secondary);
}
.msg-row.user .avatar {
  background: #141413;
  border-color: #141413;
  color: #f5f4ee;
}
.bubble {
  max-width: 76%;
  border-radius: 14px;
  padding: 12px 16px;
}
/* 助手: 无气泡裸排(Claude 风格) */
.msg-row.assistant .bubble {
  background: transparent;
  border: none;
  padding: 0;
  max-width: 82%;
}
/* 用户: 米色纸片 */
.msg-row.user .bubble {
  background: var(--bg-panel);
  border: 1px solid var(--border-color);
}
.msg-footer {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}
.meta {
  color: var(--text-secondary);
  font-size: 11.5px;
}
.typing {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--text-secondary);
  font-style: normal;
  font-size: 13px;
}
.typing span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent);
  animation: blink 1.2s infinite;
}
.typing span:nth-child(2) { animation-delay: 0.2s; }
.typing span:nth-child(3) { animation-delay: 0.4s; }
.typing em { margin-left: 8px; }
@keyframes blink {
  0%, 80%, 100% { opacity: 0.25; }
  40% { opacity: 1; }
}

/* 流式生成中: 阶段提示 + 末尾光标 */
.stage-caption {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--text-secondary);
  font-size: 12.5px;
  margin-bottom: 6px;
}
.stage-caption::before {
  content: '';
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent);
  animation: blink 1.2s infinite;
}
.stream-cursor {
  display: inline-block;
  width: 8px;
  height: 15px;
  margin-left: 2px;
  vertical-align: text-bottom;
  background: var(--accent);
  animation: blink 1s infinite;
}
.conf-row {
  margin-top: 8px;
}

.chat-input {
  border-top: 1px solid var(--border-color-lighter);
  padding: 12px 16px 14px;
}
.chat-input :deep(.el-textarea__inner) {
  background: #fcfcf9;
  border-radius: 12px;
  box-shadow: none;
}
.chat-input :deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 2px rgba(217, 119, 87, 0.25);
}
.input-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
}
.params {
  display: flex;
  align-items: center;
  gap: 8px;
}
.param-label {
  color: var(--text-secondary);
  font-size: 12.5px;
}
.send-btn {
  min-width: 110px;
  border-radius: 18px;
}
</style>
