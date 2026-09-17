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
            <div class="chat-text" v-html="renderText(msg.content)"></div>
            <SourceList v-if="msg.role === 'assistant' && msg.sources?.length" :sources="msg.sources" />
            <div v-if="msg.role === 'assistant'" class="msg-footer">
              <span class="meta">检索 {{ msg.retrievalTime }}ms · 生成 {{ msg.generationTime }}ms</span>
              <span v-if="msg.totalTokens" class="meta">{{ msg.totalTokens }} tokens</span>
            </div>
          </div>
        </div>

        <div v-if="asking" class="msg-row assistant">
          <div class="avatar"><el-icon :size="20" color="#d97757"><Shield /></el-icon></div>
          <div class="bubble">
            <div class="typing">
              <span></span><span></span><span></span>
              <em>正在检索知识库并生成回答…</em>
            </div>
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
          <el-button
            type="primary"
            class="send-btn"
            :loading="asking"
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
import { nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SourceList from '@/components/SourceList.vue'
import {
  ask, regenerate, listMessages, clearMessages, pageConversations,
  type MessageItem, type ConversationItem,
} from '@/api/chat'
import { listEnabledKb, type KnowledgeBase } from '@/api/kb'

const conversations = ref<ConversationItem[]>([])
const conversationId = ref<number | null>(null)
const messages = ref<MessageItem[]>([])
const kbList = ref<KnowledgeBase[]>([])
const knowledgeBaseId = ref<number | null>(null)
const question = ref('')
const asking = ref(false)
const topK = ref(5)
const temperature = ref(0.3)
const scrollRef = ref<HTMLDivElement>()

const quickQuestions = [
  'SQL 注入的攻击原理是什么?',
  '如何防御 XSS 跨站脚本攻击?',
  'Spring Boot 如何防止 SQL 注入?',
  'JWT 有哪些常见安全风险?',
  '什么是 OWASP API 安全的 BOLA?',
]

function renderText(text: string): string {
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  return escaped.replace(/`([^`\n]+)`/g, '<code>$1</code>')
}

function formatTime(t: string | null) {
  if (!t) return '-'
  return t.replace('T', ' ').slice(5, 16)
}

async function loadConversations() {
  const res = await pageConversations({ page: 1, size: 50 })
  conversations.value = res.records
}

function newConversation() {
  conversationId.value = null
  messages.value = []
}

async function switchConversation(id: number) {
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
  // 立即渲染用户消息
  messages.value.push({
    id: -Date.now(),
    conversationId: conversationId.value ?? 0,
    role: 'user',
    content: q,
    sources: null,
    retrievalTime: 0,
    generationTime: 0,
    totalTokens: 0,
    createdAt: new Date().toISOString(),
  })
  question.value = ''
  scrollToBottom()
  try {
    const result = await ask({
      question: q,
      conversationId: conversationId.value,
      knowledgeBaseId: knowledgeBaseId.value,
      topK: topK.value,
      temperature: temperature.value,
    })
    conversationId.value = result.conversationId
    messages.value.push({
      id: result.assistantMessageId,
      conversationId: result.conversationId,
      role: 'assistant',
      content: result.response.answer,
      sources: result.response.sources,
      retrievalTime: result.response.retrievalTime,
      generationTime: result.response.generationTime,
      totalTokens: result.response.totalTokens,
      createdAt: new Date().toISOString(),
    })
    loadConversations()
  } catch {
    messages.value = messages.value.filter((m) => m.id > 0 || m.role === 'user')
  } finally {
    asking.value = false
    scrollToBottom()
  }
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
