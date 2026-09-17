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
