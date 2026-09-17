import request from './request'

export interface KnowledgeBase {
  id: number
  name: string
  description: string | null
  category: string | null
  coverColor: string | null
  docCount: number
  chunkCount: number
  status: number
  createdBy: number | null
  createdAt: string
  updatedAt: string
}

export interface KbPage {
  records: KnowledgeBase[]
  total: number
}

export function pageKb(params: { page: number; size: number; keyword?: string; category?: string }): Promise<KbPage> {
  return request.get('/kb', { params })
}

export function listEnabledKb(): Promise<KnowledgeBase[]> {
  return request.get('/kb/enabled')
}

export function kbDetail(id: number): Promise<KnowledgeBase> {
  return request.get(`/kb/${id}`)
}

export function refreshKb(id: number): Promise<KnowledgeBase> {
  return request.post(`/kb/${id}/refresh`)
}

export function createKb(payload: { name: string; description?: string; category?: string; coverColor?: string }): Promise<KnowledgeBase> {
  return request.post('/kb', payload)
}

export function updateKb(id: number, payload: Partial<KnowledgeBase>): Promise<KnowledgeBase> {
  return request.put(`/kb/${id}`, payload)
}

export function deleteKb(id: number): Promise<void> {
  return request.delete(`/kb/${id}`)
}
