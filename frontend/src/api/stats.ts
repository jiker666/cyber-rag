import request from './request'

export interface Overview {
  kbCount: number
  documentCount: number
  chunkCount: number
  qaCount: number
  userCount: number
  conversationCount: number
  todayQaCount: number
  todayUserCount: number
}

export interface TrendPoint {
  date: string
  count: number
}

export interface CategoryStat {
  category: string
  count: number
}

export interface KbUsage {
  name: string
  value: number
}

export function fetchOverview(): Promise<Overview> {
  return request.get('/stats/overview')
}

export function fetchQaTrend(days = 7): Promise<TrendPoint[]> {
  return request.get('/stats/qa-trend', { params: { days } })
}

export function fetchHotCategories(limit = 6): Promise<CategoryStat[]> {
  return request.get('/stats/hot-categories', { params: { limit } })
}

export function fetchKbUsage(limit = 6): Promise<KbUsage[]> {
  return request.get('/stats/kb-usage', { params: { limit } })
}

export function fetchRecentQa(limit = 10): Promise<Array<Record<string, unknown>>> {
  return request.get('/stats/recent-qa', { params: { limit } })
}
