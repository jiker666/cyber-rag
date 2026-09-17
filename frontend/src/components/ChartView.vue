<template>
  <div ref="chartRef" class="chart" :style="{ height }" />
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  option: echarts.EChartsOption
  height?: string
}>()

const chartRef = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

function render() {
  if (!chartRef.value) return
  if (!chart) {
    chart = echarts.init(chartRef.value)
    chart.setOption({
      backgroundColor: 'transparent',
      textStyle: { fontFamily: 'Georgia, PingFang SC, sans-serif' },
      color: ['#d97757', '#c08a1e', '#7c9a6d', '#a98467', '#c0432f', '#8b7e74'],
      ...props.option,
    })
  } else {
    chart.setOption(props.option)
  }
}

function resize() {
  chart?.resize()
}

onMounted(() => {
  render()
  window.addEventListener('resize', resize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
})

watch(() => props.option, render, { deep: true })
</script>

<style scoped>
.chart {
  width: 100%;
}
</style>
