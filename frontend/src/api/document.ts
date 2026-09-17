import request from './request'

export interface DocumentItem {
  id: number
  knowledgeBaseId: number
  name: string
  fileType: string
  fileSize: number
  filePath: string | null
  chunkCount: number
  charCount: number
  status: 'PENDING' | 'PARSING' | 'EMBEDDING' | 'COMPLETED' | 'FAILED'
  errorMsg: string | null
  createdBy: number | null
  createdAt: string
  updatedAt: string
}

export interface DocumentPage {
  records: DocumentItem[]
  total: number
}

export function pageDocuments(params: {
  page: number
  size: number
  knowledgeBaseId?: number
  keyword?: string
  status?: string
}): Promise<DocumentPage> {
  return request.get('/documents', { params })
}

export function uploadDocument(file: File, knowledgeBaseId: number, onProgress?: (pct: number) => void): Promise<DocumentItem> {
  const form = new FormData()
  form.append('file', file)
  form.append('knowledgeBaseId', String(knowledgeBaseId))
  return request.post('/documents/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
    },
  })
}

export function reingestDocument(id: number): Promise<void> {
  return request.post(`/documents/${id}/reingest`)
}

export function deleteDocument(id: number): Promise<void> {
  return request.delete(`/documents/${id}`)
}
