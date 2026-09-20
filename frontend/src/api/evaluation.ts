import request from './request'

export interface EvalDataset {
  id: number
  name: string
  description: string | null
  itemCount: number
  createdAt: string
}

export interface EvalItem {
  id: number
  question: string
  referenceAnswer: string | null
  expectedKeywords: string | null
  expectedSource: string | null
  category: string | null
}

export interface EvalTask {
  id: number
  name: string
  mode: 'LLM_ONLY' | 'RAG_LLM'
  knowledgeBaseId: number | null
  datasetId: number
  topK: number | null
  chunkSize: number | null
  chunkOverlap: number | null
  temperature: number | null
  enableReranker: number | null
  retrievalStrategy: string | null
  /** Adaptive RAG 开关族(null = 跟随 rag-service 全局配置; 消融实验逐项关闭) */
  adaptiveEnabled: number | null
  entityBoost: number | null
  rerankGating: number | null
  dynamicContext: number | null
  useCaches: number | null
  total: number
  completed: number
  failed: number
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
  metrics: string | null
  errorMsg: string | null
  createdAt: string
}

export interface EvalMetrics {
  total?: number
  completed?: number
  failed?: number
  retrievalHitRate?: number | null
  precisionAtK?: number | null
  recallAtK?: number | null
  ndcgAtK?: number | null
  mrr?: number | null
  answerKeywordAccuracy?: number | null
  /** 引用编号有效率: [n] 是否指向真实返回来源(非事实一致性验证); 旧任务 JSON 兼容字段为 citationAccuracy */
  citationValidity?: number | null
  citationAccuracy?: number | null
  avgRetrievalTimeMs?: number | null
  avgGenerationTimeMs?: number | null
  avgTotalTimeMs?: number | null
  avgTotalTokens?: number | null
  /** Performance Detail: 重排激活率(自适应模式触发重排的题目占比) */
  rerankActivationRate?: number | null
  /** Performance Detail: 平均上下文 token 数(启发式估算口径) */
  avgContextTokens?: number | null
}

export interface EvalResult {
  id: number
  taskId: number
  itemId: number
  question: string
  mode: string
  answer: string | null
  sources: string | null
  retrievalTime: number
  generationTime: number
  totalTime: number
  promptTokens: number
  completionTokens: number
  retrievalHit: number | null
  precisionAtK: number | null
  recallAtK: number | null
  ndcgAtK: number | null
  keywordHitRate: number | null
  citationMatched: number | null
  /** Performance Detail: 自适应路由(非自适应为 null) */
  route: string | null
  /** Performance Detail: 是否触发重排(非自适应为 null) */
  rerankUsed: number | null
  /** Performance Detail: 送入 LLM 的上下文 token 数 */
  contextTokens: number | null
  manualCorrectness: number
  manualRelevance: number
  manualCompleteness: number
  manualHallucination: number
  manualScored: number
  manualComment: string | null
}

export interface TaskSummary {
  task: EvalTask
  metrics: EvalMetrics | null
  manualMetrics?: {
    scoredCount: number
    avgCorrectness: number
    avgRelevance: number
    avgCompleteness: number
    hallucinationRate: number
  }
}

export function listDatasets(): Promise<EvalDataset[]> {
  return request.get('/evaluation/datasets')
}

export function datasetItems(id: number): Promise<EvalItem[]> {
  return request.get(`/evaluation/datasets/${id}/items`)
}

export function createDataset(payload: { name: string; description?: string }): Promise<EvalDataset> {
  return request.post('/evaluation/datasets', payload)
}

export function addDatasetItems(datasetId: number, items: Array<Record<string, string>>): Promise<void> {
  return request.post(`/evaluation/datasets/${datasetId}/items`, items)
}

export function deleteDataset(id: number): Promise<void> {
  return request.delete(`/evaluation/datasets/${id}`)
}

export function listTasks(): Promise<EvalTask[]> {
  return request.get('/evaluation/tasks')
}

export function runTask(payload: {
  name: string
  mode: 'LLM_ONLY' | 'RAG_LLM'
  datasetId: number
  knowledgeBaseId?: number
  topK?: number
  chunkSize?: number
  chunkOverlap?: number
  temperature?: number
  enableReranker?: boolean
  retrievalStrategy?: string
  /** Adaptive/消融开关(undefined = 跟随全局配置) */
  adaptive?: boolean
  entityBoost?: boolean
  rerankGating?: boolean
  dynamicContext?: boolean
  useCaches?: boolean
}): Promise<EvalTask> {
  return request.post('/evaluation/tasks', payload)
}

export function taskSummary(id: number): Promise<TaskSummary> {
  return request.get(`/evaluation/tasks/${id}/summary`)
}

export function taskResults(id: number): Promise<EvalResult[]> {
  return request.get(`/evaluation/tasks/${id}/results`)
}

export function deleteTask(id: number): Promise<void> {
  return request.delete(`/evaluation/tasks/${id}`)
}

export function submitManualScore(
  resultId: number,
  payload: { correctness: number; relevance: number; completeness: number; hallucination: boolean; comment?: string },
): Promise<void> {
  return request.put(`/evaluation/results/${resultId}/manual-score`, payload)
}

export function compareTasks(taskIds: number[]): Promise<Array<Record<string, unknown>>> {
  return request.get('/evaluation/compare', { params: { taskIds: taskIds.join(',') } })
}

export function exportCsvUrl(taskId: number): string {
  return `/api/evaluation/tasks/${taskId}/export`
}
