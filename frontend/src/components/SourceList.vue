<template>
  <div class="sources">
    <div class="sources-header">
      <el-icon><Reading /></el-icon>
      <span>参考来源 ({{ sources.length }})</span>
    </div>
    <el-collapse class="sources-collapse">
      <el-collapse-item v-for="(s, i) in sources" :key="i" :name="String(i)">
        <template #title>
          <div class="source-title">
            <el-tag size="small" type="info" class="index-tag" effect="dark">[{{ i + 1 }}]</el-tag>
            <span class="doc-name">{{ s.documentName }}</span>
            <span v-if="s.page" class="page">第 {{ s.page }} 页</span>
            <el-tag size="small" :type="scoreType(s.score)" class="score-tag">
              相似度 {{ (s.score * 100).toFixed(1) }}%
            </el-tag>
            <el-tag v-if="s.rerankScore != null" size="small" type="warning" class="score-tag">
              重排 {{ s.rerankScore.toFixed(3) }}
            </el-tag>
          </div>
        </template>
        <div class="source-content">{{ s.content }}</div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup lang="ts">
import type { SourceItem } from '@/api/chat'

defineProps<{ sources: SourceItem[] }>()

function scoreType(score: number): 'success' | 'warning' | 'danger' {
  if (score >= 0.75) return 'success'
  if (score >= 0.5) return 'warning'
  return 'danger'
}
</script>

<style scoped>
.sources {
  margin-top: 12px;
  border-top: 1px dashed var(--border-color);
  padding-top: 10px;
}
.sources-header {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 12.5px;
  margin-bottom: 6px;
}
.sources-collapse {
  border-top: none;
  border-bottom: none;
}
.sources-collapse :deep(.el-collapse-item__header),
.sources-collapse :deep(.el-collapse-item__wrap) {
  background: transparent;
  border-bottom-color: var(--border-color);
}
.source-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  min-width: 0;
  flex-wrap: wrap;
}
.index-tag {
  background: var(--bg-panel);
  border-color: var(--border-color);
  color: var(--accent-strong);
}
.doc-name {
  color: var(--accent-strong);
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.page {
  color: var(--text-secondary);
  font-size: 12px;
}
.source-content {
  font-size: 13px;
  line-height: 1.7;
  color: #3d3d3a;
  background: var(--bg-base);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 10px 12px;
  white-space: pre-wrap;
}
</style>
