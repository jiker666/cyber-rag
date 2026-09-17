<template>
  <div class="page">
    <h2 class="page-title">数据看板</h2>
    <p class="page-subtitle">网络安全知识库运行状态与问答统计</p>

    <div class="stat-grid">
      <StatCard icon="Collection" label="知识库总数" :value="overview?.kbCount ?? 0" color="#d97757" />
      <StatCard icon="Folder" label="文档总数" :value="overview?.documentCount ?? 0" color="#c08a1e" />
      <StatCard icon="Grid" label="知识片段 Chunk" :value="overview?.chunkCount ?? 0" color="#7c9a6d" />
      <StatCard icon="ChatDotRound" label="累计问答次数" :value="overview?.qaCount ?? 0" color="#a98467" />
      <StatCard icon="User" label="注册用户" :value="overview?.userCount ?? 0" color="#c0432f" />
      <StatCard icon="Sunny" label="今日问答量" :value="overview?.todayQaCount ?? 0" color="#8b7e74" />
    </div>

    <el-row :gutter="16" class="chart-row">
      <el-col :span="14">
        <el-card shadow="never">
          <template #header>
            <span class="card-title">最近 7 天问答趋势</span>
          </template>
          <ChartView v-if="trend.length" :option="trendOption" height="300px" />
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="never">
          <template #header>
            <span class="card-title">知识库使用占比</span>
          </template>
          <ChartView v-if="usage.length" :option="usageOption" height="300px" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="chart-row">
      <el-col :span="10">
        <el-card shadow="never">
          <template #header>
            <span class="card-title">热门问题类别</span>
          </template>
          <ChartView v-if="categories.length" :option="categoryOption" height="280px" />
        </el-card>
      </el-col>
      <el-col :span="14">
        <el-card shadow="never">
          <template #header>
            <span class="card-title">最近问答</span>
          </template>
          <el-table :data="recentQa" size="small" :show-header="true">
            <el-table-column prop="question" label="问题" min-width="220" show-overflow-tooltip />
            <el-table-column prop="totalTime" label="耗时(ms)" width="100" align="center" />
            <el-table-column prop="createdAt" label="时间" width="170">
              <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import StatCard from '@/components/StatCard.vue'
import ChartView from '@/components/ChartView.vue'
import { fetchOverview, fetchQaTrend, fetchHotCategories, fetchKbUsage, fetchRecentQa, type Overview, type TrendPoint, type CategoryStat, type KbUsage } from '@/api/stats'
import type { EChartsOption } from 'echarts'

const overview = ref<Overview | null>(null)
const trend = ref<TrendPoint[]>([])
const categories = ref<CategoryStat[]>([])
const usage = ref<KbUsage[]>([])
const recentQa = ref<Array<Record<string, any>>>([])

const trendOption = computed<EChartsOption>(() => ({
  grid: { left: 40, right: 16, top: 30, bottom: 28 },
  tooltip: { trigger: 'axis' },
  xAxis: {
    type: 'category',
    data: trend.value.map((t) => t.date),
    axisLine: { lineStyle: { color: '#c9c4b5' } },
  },
  yAxis: { type: 'value', splitLine: { lineStyle: { color: '#e8e4d8' } }, minInterval: 1 },
  series: [
    {
      type: 'line',
      smooth: true,
      data: trend.value.map((t) => t.count),
      areaStyle: { opacity: 0.15 },
      lineStyle: { width: 2.5 },
      symbolSize: 7,
    },
  ],
}))

const usageOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} 次 ({d}%)' },
  legend: { bottom: 0, textStyle: { color: '#7c7a72', fontSize: 11 } },
  series: [
    {
      type: 'pie',
      radius: ['42%', '68%'],
      center: ['50%', '44%'],
      itemStyle: { borderRadius: 6, borderColor: '#fcfcf9', borderWidth: 2 },
      label: { show: false },
      data: usage.value.filter((u) => u.value > 0).length ? usage.value.filter((u) => u.value > 0) : [{ name: '暂无问答', value: 1 }],
    },
  ],
}))

const categoryOption = computed<EChartsOption>(() => ({
  grid: { left: 90, right: 30, top: 10, bottom: 24 },
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'value', splitLine: { lineStyle: { color: '#e8e4d8' } }, minInterval: 1 },
  yAxis: {
    type: 'category',
    data: [...categories.value].reverse().map((c) => c.category),
    axisLine: { lineStyle: { color: '#c9c4b5' } },
  },
  series: [
    {
      type: 'bar',
      barWidth: 14,
      itemStyle: { borderRadius: [0, 7, 7, 0] },
      data: [...categories.value].reverse().map((c) => c.count),
    },
  ],
}))

function formatTime(t: string) {
  return t ? t.replace('T', ' ').slice(0, 19) : '-'
}

onMounted(async () => {
  const [o, t, c, u, r] = await Promise.all([
    fetchOverview(),
    fetchQaTrend(7),
    fetchHotCategories(6),
    fetchKbUsage(6),
    fetchRecentQa(10),
  ])
  overview.value = o
  trend.value = t
  categories.value = c
  usage.value = u
  recentQa.value = r
})
</script>

<style scoped>
.stat-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 14px;
  margin-bottom: 16px;
}
@media (max-width: 1400px) {
  .stat-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
.chart-row {
  margin-bottom: 16px;
}
.card-title {
  font-weight: 600;
  font-size: 14px;
}
</style>
