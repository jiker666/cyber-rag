<template>
  <div class="page">
    <h2 class="page-title">RAG 实验</h2>
    <p class="page-subtitle">LLM Only 与 RAG + LLM 对比实验 · Top-K 实验 · Chunk Size 实验 · 支持人工评分与 CSV 导出</p>

    <!-- 发起实验 -->
    <el-card shadow="never" class="run-card">
      <template #header><span class="card-title">发起评测任务</span></template>
      <el-form :model="runForm" label-width="110px" inline>
        <el-form-item label="任务名称">
          <el-input v-model="runForm.name" placeholder="如: RAG+GLM-4 基线" style="width: 220px" />
        </el-form-item>
        <el-form-item label="实验模式">
          <el-radio-group v-model="runForm.mode">
            <el-radio-button value="LLM_ONLY">LLM Only(对照)</el-radio-button>
            <el-radio-button value="RAG_LLM">RAG + LLM</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="runForm.mode === 'RAG_LLM'" label="知识库">
          <el-select v-model="runForm.knowledgeBaseId" placeholder="选择知识库" style="width: 200px">
            <el-option v-for="kb in kbList" :key="kb.id" :label="kb.name" :value="kb.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="数据集">
          <el-select v-model="runForm.datasetId" placeholder="选择数据集" style="width: 200px">
            <el-option v-for="d in datasets" :key="d.id" :label="`${d.name} (${d.itemCount}题)`" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="runForm.mode === 'RAG_LLM'" label="Top-K">
          <el-select v-model="runForm.topK" style="width: 110px">
            <el-option v-for="k in [1, 3, 5, 10]" :key="k" :label="`K=${k}`" :value="k" />
          </el-select>
        </el-form-item>
        <el-form-item label="Temperature">
          <el-input-number v-model="runForm.temperature" :min="0" :max="2" :step="0.1" style="width: 110px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="running" @click="onRun">
            <el-icon><VideoPlay /></el-icon>&nbsp;运行实验
          </el-button>
        </el-form-item>
      </el-form>
      <el-alert type="info" :closable="false">
        <template #title>
          提示: 同一数据集分别以 LLM Only 与 RAG+LLM 运行即可完成实验一; 固定其他参数, 依次设置
          K=1/3/5/10 运行 RAG 任务即完成 Top-K 实验。所有指标均来自真实运行结果。
        </template>
      </el-alert>
    </el-card>

    <!-- 任务列表 -->
    <el-card shadow="never">
      <template #header>
        <div class="table-head">
          <span class="card-title">评测任务</span>
          <el-button
            size="small"
            :disabled="selectedTasks.length < 2"
            @click="onCompare"
          >
            对比选中任务 ({{ selectedTasks.length }})
          </el-button>
        </div>
      </template>
      <el-table :data="tasks" @selection-change="(rows: any[]) => (selectedTasks = rows)" v-loading="loadingTasks">
        <el-table-column type="selection" width="44" />
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="任务名称" min-width="150" show-overflow-tooltip />
        <el-table-column label="模式" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="row.mode === 'RAG_LLM' ? 'success' : 'warning'" size="small">
              {{ row.mode === 'RAG_LLM' ? 'RAG + LLM' : 'LLM Only' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="参数" width="150" align="center">
          <template #default="{ row }">
            <span class="mono">K={{ row.topK }}{{ row.chunkSize ? ` · CS=${row.chunkSize}` : '' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="110" align="center">
          <template #default="{ row }">{{ row.completed }}/{{ row.total }} <span v-if="row.failed" class="fail">({{ row.failed }}失败)</span></template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="taskStatusType(row.status)" size="small">{{ taskStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="openDetail(row)">结果</el-button>
            <el-button v-if="userStore.isAdmin" size="small" text @click="exportCsv(row.id)">CSV</el-button>
            <el-popconfirm title="删除任务及其全部结果?" @confirm="onDeleteTask(row.id)">
              <template #reference>
                <el-button size="small" text type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 任务详情抽屉 -->
    <el-drawer v-model="detailVisible" size="70%" :title="detailTitle">
      <template v-if="summary">
        <div class="metrics-grid">
          <div class="metric-box">
            <div class="m-title">自动指标</div>
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="检索命中率">{{ pct(summary.metrics?.retrievalHitRate) }}</el-descriptions-item>
              <el-descriptions-item label="Precision@K">{{ pct(summary.metrics?.precisionAtK) }}</el-descriptions-item>
              <el-descriptions-item label="Recall@K">{{ pct(summary.metrics?.recallAtK) }}</el-descriptions-item>
              <el-descriptions-item label="答案关键词准确率">{{ pct(summary.metrics?.answerKeywordAccuracy) }}</el-descriptions-item>
              <el-descriptions-item label="引用准确率">{{ pct(summary.metrics?.citationAccuracy) }}</el-descriptions-item>
              <el-descriptions-item label="平均总耗时">{{ ms(summary.metrics?.avgTotalTimeMs) }}</el-descriptions-item>
              <el-descriptions-item label="平均检索耗时">{{ ms(summary.metrics?.avgRetrievalTimeMs) }}</el-descriptions-item>
              <el-descriptions-item label="平均生成耗时">{{ ms(summary.metrics?.avgGenerationTimeMs) }}</el-descriptions-item>
            </el-descriptions>
          </div>
          <div class="metric-box" v-if="summary.manualMetrics">
            <div class="m-title">人工评分 ({{ summary.manualMetrics.scoredCount }} 题已评)</div>
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="正确性">{{ summary.manualMetrics.avgCorrectness.toFixed(2) }} / 5</el-descriptions-item>
              <el-descriptions-item label="相关性">{{ summary.manualMetrics.avgRelevance.toFixed(2) }} / 5</el-descriptions-item>
              <el-descriptions-item label="完整性">{{ summary.manualMetrics.avgCompleteness.toFixed(2) }} / 5</el-descriptions-item>
              <el-descriptions-item label="幻觉率">
                <span :class="summary.manualMetrics.hallucinationRate > 0.3 ? 'fail' : 'ok'">
                  {{ (summary.manualMetrics.hallucinationRate * 100).toFixed(1) }}%
                </span>
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </div>

        <el-table :data="detailResults" size="small" class="result-table" max-height="520">
          <el-table-column prop="itemId" label="题号" width="60" />
          <el-table-column prop="question" label="问题" min-width="170" show-overflow-tooltip />
          <el-table-column label="回答" min-width="220">
            <template #default="{ row }">
              <el-popover placement="left" width="420" trigger="click">
                <template #reference>
                  <span class="answer-preview">{{ (row.answer || '').slice(0, 60) || '(空)' }}</span>
                </template>
                <div class="answer-full">{{ row.answer }}</div>
              </el-popover>
            </template>
          </el-table-column>
          <el-table-column label="检索命中" width="80" align="center">
            <template #default="{ row }">
              <span v-if="row.retrievalHit === 1" class="ok">✓</span>
              <span v-else-if="row.retrievalHit === 0" class="fail">✗</span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="P@K" width="70" align="center">
            <template #default="{ row }">{{ row.precisionAtK != null ? row.precisionAtK.toFixed(2) : '-' }}</template>
          </el-table-column>
          <el-table-column label="关键词" width="80" align="center">
            <template #default="{ row }">{{ row.keywordHitRate != null ? (row.keywordHitRate * 100).toFixed(0) + '%' : '-' }}</template>
          </el-table-column>
          <el-table-column label="引用" width="70" align="center">
            <template #default="{ row }">
              <span v-if="row.citationMatched === 1" class="ok">✓</span>
              <span v-else-if="row.citationMatched === 0" class="fail">✗</span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="耗时(ms)" width="90" align="center">
            <template #default="{ row }">{{ row.totalTime }}</template>
          </el-table-column>
          <el-table-column label="人工评分" width="95" align="center">
            <template #default="{ row }">
              <span v-if="row.manualScored" class="mono">{{ row.manualCorrectness }}/{{ row.manualRelevance }}/{{ row.manualCompleteness }}{{ row.manualHallucination ? '⚠' : '' }}</span>
              <span v-else class="un-scored">未评</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80" fixed="right" v-if="userStore.isAdmin">
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click="openScore(row)">评分</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-drawer>

    <!-- 人工评分对话框 -->
    <el-dialog v-model="scoreVisible" title="人工评分" width="440px">
      <div class="score-question">问题: {{ scoreTarget?.question }}</div>
      <el-form label-width="110px">
        <el-form-item label="正确性 (1-5)">
          <el-rate v-model="scoreForm.correctness" :max="5" />
        </el-form-item>
        <el-form-item label="相关性 (1-5)">
          <el-rate v-model="scoreForm.relevance" :max="5" />
        </el-form-item>
        <el-form-item label="完整性 (1-5)">
          <el-rate v-model="scoreForm.completeness" :max="5" />
        </el-form-item>
        <el-form-item label="是否存在幻觉">
          <el-switch v-model="scoreForm.hallucination" active-text="存在" inactive-text="不存在" />
        </el-form-item>
        <el-form-item label="评语">
          <el-input v-model="scoreForm.comment" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="scoreVisible = false">取消</el-button>
        <el-button type="primary" @click="onSubmitScore">提交评分</el-button>
      </template>
    </el-dialog>

    <!-- 对比结果对话框 -->
    <el-dialog v-model="compareVisible" title="多任务指标对比" width="900px">
      <el-table :data="compareRows" size="small" border>
        <el-table-column prop="name" label="任务" min-width="140" fixed="left" />
        <el-table-column prop="mode" label="模式" width="100" align="center" />
        <el-table-column prop="topK" label="K" width="50" align="center" />
        <el-table-column label="检索命中率" width="100" align="center">
          <template #default="{ row }">{{ pct(row.metrics?.retrievalHitRate) }}</template>
        </el-table-column>
        <el-table-column label="P@K" width="80" align="center">
          <template #default="{ row }">{{ pct(row.metrics?.precisionAtK) }}</template>
        </el-table-column>
        <el-table-column label="关键词准确率" width="110" align="center">
          <template #default="{ row }">{{ pct(row.metrics?.answerKeywordAccuracy) }}</template>
        </el-table-column>
        <el-table-column label="引用准确率" width="100" align="center">
          <template #default="{ row }">{{ pct(row.metrics?.citationAccuracy) }}</template>
        </el-table-column>
        <el-table-column label="平均耗时" width="95" align="center">
          <template #default="{ row }">{{ ms(row.metrics?.avgTotalTimeMs) }}</template>
        </el-table-column>
        <el-table-column label="平均Token" width="95" align="center">
          <template #default="{ row }">{{ row.metrics?.avgTotalTokens?.toFixed(0) ?? '-' }}</template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import {
  listDatasets, listTasks, runTask, taskSummary, taskResults, deleteTask,
  submitManualScore, compareTasks, type EvalDataset, type EvalTask, type EvalResult, type TaskSummary,
} from '@/api/evaluation'
import { listEnabledKb, type KnowledgeBase } from '@/api/kb'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const datasets = ref<EvalDataset[]>([])
const kbList = ref<KnowledgeBase[]>([])
const tasks = ref<EvalTask[]>([])
const selectedTasks = ref<EvalTask[]>([])
const loadingTasks = ref(false)
const running = ref(false)

const runForm = reactive<{
  name: string
  mode: 'LLM_ONLY' | 'RAG_LLM'
  datasetId: number | null
  knowledgeBaseId: number | null
  topK: number
  temperature: number
}>({ name: '', mode: 'RAG_LLM', datasetId: null, knowledgeBaseId: null, topK: 5, temperature: 0.3 })

const detailVisible = ref(false)
const detailTitle = ref('')
const summary = ref<TaskSummary | null>(null)
const detailResults = ref<EvalResult[]>([])

const scoreVisible = ref(false)
const scoreTarget = ref<EvalResult | null>(null)
const scoreForm = reactive({ correctness: 3, relevance: 3, completeness: 3, hallucination: false, comment: '' })

const compareVisible = ref(false)
const compareRows = ref<Array<any>>([])

function formatTime(t: string) {
  return t ? t.replace('T', ' ').slice(0, 19) : '-'
}
function pct(v?: number | null) {
  return v == null ? '-' : (v * 100).toFixed(1) + '%'
}
function ms(v?: number | null) {
  return v == null ? '-' : v.toFixed(0) + 'ms'
}
function taskStatusType(s: string) {
  return { COMPLETED: 'success', FAILED: 'danger', RUNNING: 'warning', PENDING: 'info' }[s] || 'info'
}
function taskStatusText(s: string) {
  return { COMPLETED: '已完成', FAILED: '失败', RUNNING: '运行中', PENDING: '等待' }[s] || s
}

async function loadTasks() {
  loadingTasks.value = true
  try {
    tasks.value = await listTasks()
    const anyRunning = tasks.value.some((t) => t.status === 'RUNNING' || t.status === 'PENDING')
    if (anyRunning) setTimeout(loadTasks, 4000)
  } finally {
    loadingTasks.value = false
  }
}

async function onRun() {
  if (!runForm.name.trim()) {
    ElMessage.warning('请输入任务名称')
    return
  }
  if (!runForm.datasetId) {
    ElMessage.warning('请选择数据集')
    return
  }
  if (runForm.mode === 'RAG_LLM' && !runForm.knowledgeBaseId) {
    ElMessage.warning('RAG 模式请选择知识库')
    return
  }
  running.value = true
  try {
    await runTask({
      name: runForm.name,
      mode: runForm.mode,
      datasetId: runForm.datasetId,
      knowledgeBaseId: runForm.knowledgeBaseId ?? undefined,
      topK: runForm.topK,
      temperature: runForm.temperature,
    })
    ElMessage.success('任务已创建, 正在后台运行')
    loadTasks()
  } finally {
    running.value = false
  }
}

async function openDetail(task: EvalTask) {
  detailTitle.value = `任务 #${task.id} · ${task.name}`
  const [s, r] = await Promise.all([taskSummary(task.id), taskResults(task.id)])
  summary.value = s
  detailResults.value = r
  detailVisible.value = true
}

async function onDeleteTask(id: number) {
  await deleteTask(id)
  ElMessage.success('已删除')
  loadTasks()
}

function exportCsv(taskId: number) {
  const token = localStorage.getItem('cyberrag_token')
  axios
    .get(`/api/evaluation/tasks/${taskId}/export`, {
      responseType: 'blob',
      headers: { Authorization: `Bearer ${token}` },
    })
    .then((resp) => {
      const url = URL.createObjectURL(resp.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `eval_task_${taskId}.csv`
      a.click()
      URL.revokeObjectURL(url)
    })
}

function openScore(row: EvalResult) {
  scoreTarget.value = row
  scoreForm.correctness = row.manualCorrectness || 3
  scoreForm.relevance = row.manualRelevance || 3
  scoreForm.completeness = row.manualCompleteness || 3
  scoreForm.hallucination = row.manualHallucination === 1
  scoreForm.comment = row.manualComment || ''
  scoreVisible.value = true
}

async function onSubmitScore() {
  if (!scoreTarget.value) return
  await submitManualScore(scoreTarget.value.id, { ...scoreForm })
  ElMessage.success('评分已提交')
  scoreVisible.value = false
  // 刷新详情
  if (summary.value?.task) openDetail(summary.value.task)
}

async function onCompare() {
  const ids = selectedTasks.value.map((t) => t.id)
  compareRows.value = await compareTasks(ids)
  compareVisible.value = true
}

const detailTask = computed(() => summary.value?.task)

onMounted(async () => {
  datasets.value = await listDatasets()
  if (datasets.value.length) runForm.datasetId = datasets.value[0].id
  kbList.value = await listEnabledKb()
  if (kbList.value.length) runForm.knowledgeBaseId = kbList.value[0].id
  loadTasks()
})
</script>

<style scoped>
.card-title {
  font-weight: 600;
  font-size: 14px;
}
.run-card {
  margin-bottom: 16px;
}
.table-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.mono {
  font-family: 'JetBrains Mono', Menlo, monospace;
  font-size: 12px;
}
.fail {
  color: var(--danger);
}
.ok {
  color: var(--success);
}
.un-scored {
  color: var(--text-secondary);
  font-size: 12px;
}
.metrics-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 16px;
}
.metric-box .m-title {
  font-weight: 600;
  margin-bottom: 8px;
  font-size: 13.5px;
}
.answer-preview {
  cursor: pointer;
  color: var(--accent-strong);
}
.answer-full {
  max-height: 360px;
  overflow-y: auto;
  white-space: pre-wrap;
  line-height: 1.7;
  font-size: 13px;
}
.score-question {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 14px;
}
.result-table {
  width: 100%;
}
</style>
