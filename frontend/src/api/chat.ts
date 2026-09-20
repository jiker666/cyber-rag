import request from './request'

export interface SourceItem {
  documentId: number
  documentName: string
  knowledgeBaseId: number
  chunkIndex: number
  source: string
  page: number | null
  content: string
  score: number | null
  rerankScore: number | null
  /** 命中通道: vector / bm25 / both */
  matchType: string
  /** 是否被安全实体精确加权提升 */
  entityMatched: boolean
  /** 小到大检索的父块 ID(子块命中后返回父块上下文) */
  parentChunkId: number | null
}

/** 单次问答的性能与决策轨迹(字段与 rag-service RagTrace.to_dict 一一对应) */
export interface RagTrace {
  queryAnalysisMs: number
  embeddingMs: number
  vectorSearchMs: number
  bm25SearchMs: number
  fusionMs: number
  rerankMs: number
  contextBuildMs: number
  /** LLM 首 token 延迟(流式路径) */
  llmTtftMs: number
  generationMs: number
  totalMs: number
  route: string
  routeReason: string
  queryType: string
  rerankerUsed: boolean
  rerankReason: string
  entityBoosted: boolean
  embeddingCacheHit: boolean
  retrievalCacheHit: boolean
  candidateCount: number
  finalContextCount: number
  contextTokens: number
  droppedChunks: number
  retrievalConfidence: number | null
  confidenceLevel: string
}

/** Security-Aware 查询分析结果(纯规则, 无 LLM) */
export interface QueryAnalysis {
  queryType: string
  complexity: number
  securityEntities: string[]
  entityTypes: Record<string, string[]>
  exactIdentifiers: string[]
  keywords: string[]
  needsMultiHop: boolean
  recommendedStrategy: string
  recommendedTopK: number
  needRerank: boolean
  confidence: number
  analysisMs: number
}

/** 自适应路由决策 */
export interface RouteDecision {
  route: string
  strategy: string
  topK: number
  rerankPolicy: string
  needDecompose: boolean
  reason: string
}

/** 证据置信度 */
export interface EvidenceConfidence {
  retrievalConfidence: number
  level: 'sufficient' | 'moderate' | 'insufficient'
  label: string
}

export interface ChatResponse {
  answer: string
  sources: SourceItem[]
  retrievalTime: number
  generationTime: number
  totalTime: number
  promptTokens: number
  completionTokens: number
  totalTokens: number
  retrievedCount: number
  trace: RagTrace | null
  analysis: QueryAnalysis | null
  route: RouteDecision | null
  confidence: EvidenceConfidence | null
}

export interface AskPayload {
  question: string
  conversationId?: number | null
  knowledgeBaseId: number
  topK?: number
  temperature?: number
  enableReranker?: boolean
}

export interface AskResult {
  conversationId: number
  userMessageId: number
  assistantMessageId: number
  response: ChatResponse
}

export interface MessageItem {
  id: number
  conversationId: number
  role: 'user' | 'assistant'
  content: string
  sources: SourceItem[] | null
  /** 本次 RAG 决策轨迹(历史消息由 message.trace 返回) */
  trace: RagTrace | null
  retrievalTime: number
  generationTime: number
  totalTokens: number
  createdAt: string
}

export interface ConversationItem {
  id: number
  userId: number
  title: string
  knowledgeBaseId: number | null
  messageCount: number
  lastMessageAt: string | null
  createdAt: string
}

export function ask(payload: AskPayload): Promise<AskResult> {
  return request.post('/chat/ask', payload)
}

export function regenerate(conversationId: number): Promise<AskResult> {
  return request.post(`/chat/conversations/${conversationId}/regenerate`)
}

export function listMessages(conversationId: number): Promise<MessageItem[]> {
  return request.get(`/chat/conversations/${conversationId}/messages`)
}

export function clearMessages(conversationId: number): Promise<void> {
  return request.delete(`/chat/conversations/${conversationId}/messages`)
}

export function pageConversations(params: { page: number; size: number }): Promise<{ records: ConversationItem[]; total: number }> {
  return request.get('/chat/conversations', { params })
}

export function renameConversation(id: number, title: string): Promise<void> {
  return request.put(`/chat/conversations/${id}/title`, { title })
}

export function deleteConversation(id: number): Promise<void> {
  return request.delete(`/chat/conversations/${id}`)
}

export function submitFeedback(payload: { messageId: number; rating: 1 | -1; comment?: string }): Promise<void> {
  return request.post('/feedback', payload)
}

// ------------------------------------------------------------------
// 流式问答(SSE)
// ------------------------------------------------------------------

/** SSE 事件回调: start → analysis → retrieval → delta×N → done / error */
export interface StreamHandlers {
  onStart?: (e: { conversationId: number; userMessageId: number }) => void
  onAnalysis?: (e: { analysis: QueryAnalysis; route: RouteDecision }) => void
  onRetrieval?: (e: { sources: SourceItem[]; confidence: EvidenceConfidence }) => void
  onDelta?: (text: string) => void
  onDone?: (e: { assistantMessageId: number; response: ChatResponse }) => void
  onError?: (message: string) => void
}

/**
 * 流式问答: 裸 fetch 逐行读取 SSE(axios 不支持 ReadableStream 渐进读取)。
 *
 * 事件: start(会话/消息 ID) → analysis(问题分析+路由) → retrieval(候选+置信度)
 *       → delta(增量文本)×N → done(完整结果, 含 trace) / error
 * 401 时清理本地凭据并跳转登录(与 axios 拦截器行为一致)。
 * options.signal 中止时静默返回(不触发 onError), 已收到的增量文本由调用方决定去留。
 */
export async function askStream(
  payload: AskPayload,
  handlers: StreamHandlers,
  options?: { signal?: AbortSignal },
): Promise<void> {
  const token = localStorage.getItem('cyberrag_token')
  let resp: Response
  try {
    resp = await fetch('/api/chat/ask/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(payload),
      signal: options?.signal,
    })
  } catch (e: any) {
    if (e?.name !== 'AbortError') handlers.onError?.(e?.message || '无法连接服务器')
    return
  }

  if (resp.status === 401) {
    localStorage.removeItem('cyberrag_token')
    localStorage.removeItem('cyberrag_user')
    handlers.onError?.('登录已过期, 请重新登录')
    const { default: router } = await import('@/router')
    router.push({ name: 'login' })
    return
  }
  if (!resp.ok || !resp.body) {
    let message = `请求错误 (${resp.status})`
    try {
      const data = await resp.json()
      if (data?.message) message = data.message
    } catch { /* 非 JSON 错误体 */ }
    handlers.onError?.(message)
    return
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  const dispatch = (line: string) => {
    const trimmed = line.trim()
    if (!trimmed.startsWith('data:')) return
    const json = trimmed.slice(5).trim()
    if (!json) return
    let event: any
    try {
      event = JSON.parse(json)
    } catch {
      return
    }
    switch (event.type) {
      case 'start': handlers.onStart?.(event); break
      case 'analysis': handlers.onAnalysis?.(event); break
      case 'retrieval': handlers.onRetrieval?.(event); break
      case 'delta': handlers.onDelta?.(event.text ?? ''); break
      case 'done': handlers.onDone?.(event); break
      case 'error': handlers.onError?.(event.message || 'AI 服务流式调用失败'); break
    }
  }

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let nl: number
      while ((nl = buffer.indexOf('\n')) >= 0) {
        dispatch(buffer.slice(0, nl))
        buffer = buffer.slice(nl + 1)
      }
    }
    if (buffer) dispatch(buffer)
  } catch (e: any) {
    // 手动停止: 不当错误处理, partial 内容保留给调用方
    if (e?.name !== 'AbortError') handlers.onError?.(e?.message || '流式连接中断')
  }
}
