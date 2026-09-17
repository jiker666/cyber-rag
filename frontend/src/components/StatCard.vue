<template>
  <div class="stat-card panel-card">
    <div class="stat-icon" :style="{ background: color + '22', color }">
      <el-icon :size="24"><component :is="icon" /></el-icon>
    </div>
    <div class="stat-body">
      <div class="stat-value">{{ displayValue }}</div>
      <div class="stat-label">{{ label }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, type Component } from 'vue'

const props = defineProps<{
  icon: string | Component
  label: string
  value: number
  color?: string
}>()

const color = computed(() => props.color || '#d97757')
const displayValue = computed(() =>
  props.value >= 10000 ? (props.value / 10000).toFixed(1) + 'w' : props.value.toLocaleString(),
)
</script>

<style scoped>
.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
}
.stat-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stat-value {
  font-size: 27px;
  font-weight: 600;
  font-family: var(--font-serif);
}
.stat-label {
  color: var(--text-secondary);
  font-size: 13px;
  margin-top: 2px;
}
</style>
