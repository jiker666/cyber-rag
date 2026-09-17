import request from './request'

export interface RagConfig {
  id: number
  chunkSize: number
  chunkOverlap: number
  topK: number
  temperature: number
  scoreThreshold: number
  enableReranker: number
  rerankTopN: number
  retrievalStrategy: string
  historyWindow: number
  updatedAt: string
}

export function fetchRagConfig(): Promise<RagConfig> {
  return request.get('/rag-config')
}

export function updateRagConfig(config: Partial<RagConfig>): Promise<RagConfig> {
  return request.put('/rag-config', config)
}

export interface RuntimeInfo {
  embedding: { provider: string; model: string; dimension?: number }
  llm: { provider: string; model: string; error?: string }
  reranker: { enabled: boolean; model: string }
  vectorStore: { type: string; persistDir: string }
  retrieval: { strategy: string }
  defaults: Record<string, number>
}

export function fetchRuntimeInfo(): Promise<RuntimeInfo> {
  return request.get('/rag-config/runtime')
}
