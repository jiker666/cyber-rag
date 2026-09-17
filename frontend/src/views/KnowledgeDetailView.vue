<template>
  <div class="page">
    <div class="detail-head panel-card" v-if="kb">
      <div class="color-bar" :style="{ background: kb.coverColor || '#d97757' }"></div>
      <div class="head-body">
        <div class="head-info">
          <div class="head-title-row">
            <h2 class="page-title" style="margin: 0">{{ kb.name }}</h2>
            <el-tag size="small">{{ kb.category || '未分类' }}</el-tag>
            <el-tag v-if="kb.status === 1" size="small" type="success">启用</el-tag>
          </div>
          <p class="desc">{{ kb.description || '暂无简介' }}</p>
          <div class="head-stats">
            <span><b>{{ kb.docCount }}</b> 篇文档</span>
            <span><b>{{ kb.chunkCount }}</b> 个知识片段</span>
            <span>更新于 {{ formatTime(kb.updatedAt) }}</span>
          </div>
        </div>
        <div class="head-actions" v-if="userStore.isAdmin">
          <el-button @click="onSync"><el-icon><Refresh /></el-icon>&nbsp;同步统计</el-button>
          <el-button :disabled="!kb.docCount" @click="goDocuments">
            <el-icon><Upload /></el-icon>&nbsp;管理文档
          </el-button>
          <el-popconfirm title="删除知识库(需先清空文档), 确认?" @confirm="onDelete">
            <template #reference>
              <el-button type="danger" plain><el-icon><Delete /></el-icon>&nbsp;删除</el-button>
            </template>
          </el-popconfirm>
        </div>
      </div>
    </div>

    <el-card shadow="never">
      <template #header>
        <div class="table-head">
          <span>知识库文档</span>
          <el-button v-if="userStore.isAdmin" type="primary" size="small" @click="goDocuments">
            上传文档
          </el-button>
        </div>
      </template>
      <el-table :data="documents" v-loading="loading">
        <el-table-column prop="name" label="文档名称" min-width="240" show-overflow-tooltip />
        <el-table-column prop="fileType" label="类型" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.fileType }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="chunkCount" label="Chunk 数" width="100" align="center" />
        <el-table-column prop="status" label="状态" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="100" align="center">
          <template #default="{ row }">{{ (row.fileSize / 1024).toFixed(0) }} KB</template>
        </el-table-column>
        <el-table-column label="上传时间" width="170">
          <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
        </el-table-column>
        <el-table-column prop="errorMsg" label="错误信息" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.errorMsg || '-' }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { kbDetail, refreshKb, deleteKb, type KnowledgeBase } from '@/api/kb'
import { pageDocuments, type DocumentItem } from '@/api/document'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const kb = ref<KnowledgeBase | null>(null)
const documents = ref<DocumentItem[]>([])
const loading = ref(false)

function formatTime(t: string) {
  return t ? t.replace('T', ' ').slice(0, 19) : '-'
}

function statusType(s: string) {
  return { COMPLETED: 'success', FAILED: 'danger', PENDING: 'info', PARSING: 'warning', EMBEDDING: 'warning' }[s] || 'info'
}

function statusText(s: string) {
  return { COMPLETED: '处理完成', FAILED: '处理失败', PENDING: '等待处理', PARSING: '解析中', EMBEDDING: '向量化中' }[s] || s
}

async function load() {
  loading.value = true
  try {
    const id = Number(route.params.id)
    kb.value = await kbDetail(id)
    const res = await pageDocuments({ page: 1, size: 50, knowledgeBaseId: id })
    documents.value = res.records
  } finally {
    loading.value = false
  }
}

async function onSync() {
  if (!kb.value) return
  kb.value = await refreshKb(kb.value.id)
  ElMessage.success('已同步')
  load()
}

function goDocuments() {
  router.push({ path: '/documents', query: { knowledgeBaseId: String(kb.value?.id || '') } })
}

async function onDelete() {
  if (!kb.value) return
  await deleteKb(kb.value.id)
  ElMessage.success('已删除')
  router.push('/knowledge')
}

onMounted(load)
</script>

<style scoped>
.detail-head {
  position: relative;
  overflow: hidden;
  margin-bottom: 16px;
}
.color-bar {
  height: 4px;
}
.head-body {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 20px;
}
.head-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.desc {
  color: var(--text-secondary);
  font-size: 13px;
  margin: 8px 0 12px;
}
.head-stats {
  display: flex;
  gap: 20px;
  color: var(--text-secondary);
  font-size: 13px;
}
.head-stats b {
  color: var(--accent);
  font-size: 15px;
}
.head-actions {
  display: flex;
  flex-direction: column;
  gap: 0;
  justify-content: center;
}
.head-actions .el-button {
  margin: 0 0 8px 0;
}
.table-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
