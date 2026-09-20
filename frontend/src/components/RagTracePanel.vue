<template>
  <div class="trace-panel">
    <el-collapse v-model="opened">
      <el-collapse-item name="trace">
        <template #title>
          <div class="trace-title">
            <el-icon><DataAnalysis /></el-icon>
            <span>本次 RAG 决策</span>
            <el-tag size="small" :type="routeType" effect="plain">{{ routeLabel }}</el-tag>
            <el-tag size="small" :type="trace.rerankerUsed ? 'warning' : 'info'" effect="plain">
              {{ trace.rerankerUsed ? '已重排' : '跳过重排' }}
            </el-tag>
            <span class="trace-total">{{ trace.totalMs }}ms</span>
          </div>
        </template>

        <div class="trace-body">
          <!-- 查询分析 -->
          <div class="trace-section">
            <div class="section-label">查询分析</div>
            <div class="kv-row">
              <span class="k">问题类型</span>
              <span class="v">{{ queryTypeLabel }}</span>
              <span class="k">复杂度</span>
              <span class="v">{{ analysis?.complexity ?? '-' }}</span>
              <span class="k">实体加权</span>
              <span class="v">{{ trace.entityBoosted ? '已启用' : '未触发' }}</span>
            </div>
            <div v-if="entityList.length" class="kv-row">
              <span class="k">识别实体</span>
              <span class="v entities">
                <el-tag v-for="e in entityList" :key="e" size="small" effect="plain" class="entity-tag">{{ e }}</el-tag>
              </span>
            </div>
          </div>

          <!-- 路由与门控 -->
          <div class="trace-section">
            <div class="section-label">检索路由</div>
            <div class="kv-row">
              <span class="k">路径</span>
              <span class="v">{{ routeLabel }}</span>
              <span class="k">策略</span>
              <span class="v mono">{{ routeStrategy }}</span>
            </div>
            <div class="reason">{{ trace.routeReason || '-' }}</div>
            <div class="kv-row">
              <span class="k">重排决策</span>
              <span class="v">{{ trace.rerankerUsed ? '执行交叉编码器重排' : '按置信度门控跳过' }}</span>
            </div>
            <div v-if="trace.rerankReason" class="reason">{{ trace.rerankReason }}</div>
          </div>

          <!-- 上下文构建 -->
          <div class="trace-section">
            <div class="section-label">上下文构建</div>
            <div class="kv-row">
              <span class="k">候选片段</span>
              <span class="v">{{ trace.candidateCount }}</span>
              <span class="k">最终上下文</span>
              <span class="v">{{ trace.finalContextCount }}</span>
              <span class="k">预算裁剪</span>
              <span class="v">{{ trace.droppedChunks }}</span>
              <span class="k">上下文规模</span>
              <span class="v">≈ {{ trace.contextTokens }} tokens</span>
            </div>
          </div>

          <!-- 阶段耗时 -->
          <div class="trace-section">
            <div class="section-label">阶段耗时 (ms)</div>
            <div class="timing-grid">
              <div v-for="t in timings" :key="t.label" class="timing-item" :class="{ zero: !t.value }">
                <span class="t-label">{{ t.label }}</span>
                <span class="t-value">{{ t.value || '-' }}</span>
              </div>
            </div>
          </div>

          <!-- 缓存 -->
          <div class="trace-section">
            <div class="section-label">缓存命中</div>
            <div class="kv-row">
              <span class="k">Embedding</span>
              <span class="v">
                <el-tag size="small" :type="trace.embeddingCacheHit ? 'success' : 'info'" effect="plain">
                  {{ trace.embeddingCacheHit ? '命中' : '未命中' }}
                </el-tag>
              </span>
              <span class="k">检索结果</span>
              <span class="v">
                <el-tag size="small" :type="trace.retrievalCacheHit ? 'success' : 'info'" effect="plain">
                  {{ trace.retrievalCacheHit ? '命中' : '未命中' }}
                </el-tag>
              </span>
            </div>
          </div>
        </div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { RagTrace, QueryAnalysis } from '@/api/chat'

const props = defineProps<{
  trace: RagTrace
  analysis?: QueryAnalysis | null
  /** 管理员默认展开(调试视角), 普通用户默认折叠 */
  defaultOpen?: boolean
}>()

const opened = ref<string[]>(props.defaultOpen ? ['trace'] : [])

const QUERY_TYPES: Record<string, string> = {
  EXACT_ENTITY: '精确实体',
  FACTUAL: '简单事实',
  PROCEDURAL: '操作流程',
  CONCEPT: '概念解释',
  COMPARATIVE: '对比分析',
  MULTI_HOP: '多跳推理',
}

const ROUTES: Record<string, { label: string; type: 'success' | 'warning' | 'primary' | 'danger' | 'info' }> = {
  EXACT: { label: 'EXACT 精确匹配', type: 'success' },
  FAST: { label: 'FAST 快速通道', type: 'primary' },
  HYBRID: { label: 'HYBRID 混合检索', type: 'warning' },
  DECOMPOSE: { label: 'DECOMPOSE 分解检索', type: 'danger' },
}

const queryTypeLabel = computed(() => QUERY_TYPES[props.trace.queryType] || props.trace.queryType || '-')
const routeLabel = computed(() => ROUTES[props.trace.route]?.label || props.trace.route || '固定策略')
const routeType = computed(() => ROUTES[props.trace.route]?.type || 'info')
const routeStrategy = computed(() => {
  const t = props.trace
  if (t.bm25SearchMs > 0 || t.route === 'EXACT' || t.route === 'HYBRID' || t.route === 'DECOMPOSE') return 'hybrid'
  if (t.route === 'FAST') return 'vector(top3)'
  return t.route ? 'vector' : '-'
})

const entityList = computed(() => {
  const fromAnalysis = props.analysis?.securityEntities ?? []
  const fromTypes = Object.values(props.analysis?.entityTypes ?? {}).flat()
  const merged = new Set<string>([...fromAnalysis, ...fromTypes])
  return [...merged].slice(0, 8)
})

const timings = computed(() => [
  { label: '查询分析', value: props.trace.queryAnalysisMs },
  { label: 'Embedding', value: props.trace.embeddingMs },
  { label: '向量检索', value: props.trace.vectorSearchMs },
  { label: 'BM25', value: props.trace.bm25SearchMs },
  { label: 'RRF 融合', value: props.trace.fusionMs },
  { label: '重排', value: props.trace.rerankMs },
  { label: '上下文构建', value: props.trace.contextBuildMs },
  { label: '首字延迟', value: props.trace.llmTtftMs },
  { label: '生成', value: props.trace.generationMs },
  { label: '总耗时', value: props.trace.totalMs },
])
</script>

<style scoped>
.trace-panel {
  margin-top: 10px;
  border-top: 1px dashed var(--border-color);
  padding-top: 6px;
}
.trace-panel :deep(.el-collapse) {
  border-top: none;
  border-bottom: none;
}
.trace-panel :deep(.el-collapse-item__header),
.trace-panel :deep(.el-collapse-item__wrap) {
  background: transparent;
  border-bottom-color: var(--border-color);
  height: 34px;
  line-height: 34px;
}
.trace-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  color: var(--text-secondary);
}
.trace-total {
  margin-left: auto;
  margin-right: 24px;
  font-family: 'JetBrains Mono', Menlo, monospace;
  font-size: 11.5px;
  color: var(--text-secondary);
}
.trace-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 4px 0 12px;
}
.trace-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.section-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent-strong);
}
.kv-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 12.5px;
}
.kv-row .k {
  color: var(--text-secondary);
}
.kv-row .v {
  color: var(--text-primary);
}
.v.entities {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.entity-tag {
  font-family: 'JetBrains Mono', Menlo, monospace;
  font-size: 11px;
}
.v.mono {
  font-family: 'JetBrains Mono', Menlo, monospace;
}
.reason {
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--bg-base);
  border: 1px solid var(--border-color-lighter);
  border-radius: 6px;
  padding: 5px 8px;
  line-height: 1.6;
}
.timing-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 6px;
}
.timing-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  background: var(--bg-base);
  border: 1px solid var(--border-color-lighter);
  border-radius: 6px;
  padding: 5px 2px;
}
.timing-item.zero {
  opacity: 0.45;
}
.t-label {
  font-size: 11px;
  color: var(--text-secondary);
}
.t-value {
  font-family: 'JetBrains Mono', Menlo, monospace;
  font-size: 12.5px;
  color: var(--accent-strong);
}
</style>
