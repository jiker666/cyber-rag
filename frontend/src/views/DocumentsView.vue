<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2 class="page-title">文档管理</h2>
        <p class="page-subtitle" style="margin-bottom: 0">
          上传网络安全文档: 解析 → 清洗 → 切片 → 向量化 → 写入向量库
        </p>
      </div>
      <div class="head-actions">
        <el-select v-model="filterKb" placeholder="全部知识库" clearable style="width: 200px" @change="load">
          <el-option v-for="kb in kbList" :key="kb.id" :label="kb.name" :value="kb.id" />
        </el-select>
        <el-button v-if="userStore.isAdmin" type="primary" @click="uploadVisible = true">
          <el-icon><Upload /></el-icon>&nbsp;上传文档
        </el-button>
      </div>
    </div>

    <el-card shadow="never">
      <el-table :data="records" v-loading="loading">
        <el-table-column prop="name" label="文档名称" min-width="240" show-overflow-tooltip />
        <el-table-column label="知识库" width="150">
          <template #default="{ row }">{{ kbMap[row.knowledgeBaseId] || row.knowledgeBaseId }}</template>
        </el-table-column>
        <el-table-column prop="fileType" label="类型" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.fileType }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="chunkCount" label="Chunk 数" width="95" align="center" />
        <el-table-column prop="status" label="状态" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">
              {{ row.status === 'EMBEDDING' ? '向量化中' : row.status === 'PARSING' ? '解析中' : row.status === 'COMPLETED' ? '处理完成' : row.status === 'FAILED' ? '处理失败' : '等待处理' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="90" align="center">
          <template #default="{ row }">{{ (row.fileSize / 1024).toFixed(0) }} KB</template>
        </el-table-column>
        <el-table-column prop="errorMsg" label="错误信息" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.errorMsg || '-' }}</template>
        </el-table-column>
        <el-table-column v-if="userStore.isAdmin" label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" :disabled="isProcessing(row)" @click="onReingest(row)">
              重新向量化
            </el-button>
            <el-popconfirm title="删除文档将同时清除向量数据, 确认?" @confirm="onDelete(row.id)">
              <template #reference>
                <el-button size="small" text type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          :page-size="size"
          :total="total"
          layout="prev, pager, next, total"
          @current-change="load"
        />
      </div>
    </el-card>

    <!-- 上传对话框 -->
    <el-dialog v-model="uploadVisible" title="上传知识文档" width="500px" @closed="resetUpload">
      <el-form label-width="90px">
        <el-form-item label="目标知识库" required>
          <el-select v-model="uploadKbId" placeholder="选择知识库" style="width: 100%">
            <el-option v-for="kb in kbList" :key="kb.id" :label="kb.name" :value="kb.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="文件" required>
          <el-upload
            drag
            :auto-upload="false"
            :limit="1"
            :on-change="onFileChange"
            :on-remove="() => (uploadFile = null)"
            accept=".pdf,.txt,.md,.markdown,.docx"
          >
            <el-icon :size="40" color="#d97757"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽文件到此处, 或 <em>点击选择</em></div>
            <template #tip>
              <div class="el-upload__tip">支持 PDF / TXT / Markdown / DOCX, 单文件 ≤ 20MB</div>
            </template>
          </el-upload>
        </el-form-item>
        <el-progress v-if="uploading" :percentage="uploadPct" :stroke-width="8" />
      </el-form>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" :disabled="!uploadFile || !uploadKbId" @click="onUpload">
          {{ uploading ? '解析入库中…' : '上传并入库' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'
import {
  pageDocuments, uploadDocument, reingestDocument, deleteDocument, type DocumentItem,
} from '@/api/document'
import { listEnabledKb, type KnowledgeBase } from '@/api/kb'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const userStore = useUserStore()
const records = ref<DocumentItem[]>([])
const kbList = ref<KnowledgeBase[]>([])
const kbMap = ref<Record<number, string>>({})
const loading = ref(false)
const page = ref(1)
const size = 10
const total = ref(0)
const filterKb = ref<number | undefined>()

const uploadVisible = ref(false)
const uploadKbId = ref<number | null>(null)
const uploadFile = ref<File | null>(null)
const uploading = ref(false)
const uploadPct = ref(0)
let pollTimer: number | null = null

async function load() {
  loading.value = true
  try {
    const res = await pageDocuments({
      page: page.value,
      size,
      knowledgeBaseId: filterKb.value,
    })
    records.value = res.records
    total.value = res.total
    // 存在处理中的文档时轮询刷新
    const processing = res.records.some((r) => r.status === 'PENDING' || r.status === 'PARSING' || r.status === 'EMBEDDING')
    if (processing && !pollTimer) {
      pollTimer = window.setInterval(load, 3000)
    } else if (!processing && pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  } finally {
    loading.value = false
  }
}

function statusType(s: string) {
  return { COMPLETED: 'success', FAILED: 'danger', PENDING: 'info', PARSING: 'warning', EMBEDDING: 'warning' }[s] || 'info'
}

function isProcessing(row: DocumentItem) {
  return ['PENDING', 'PARSING', 'EMBEDDING'].includes(row.status)
}

function onFileChange(file: UploadFile) {
  uploadFile.value = (file.raw as File) || null
}

async function onUpload() {
  if (!uploadFile.value || !uploadKbId.value) return
  const allowed = ['.pdf', '.txt', '.md', '.markdown', '.docx']
  const name = uploadFile.value.name.toLowerCase()
  if (!allowed.some((ext) => name.endsWith(ext))) {
    ElMessage.error('仅支持 PDF / TXT / Markdown / DOCX 格式')
    return
  }
  if (uploadFile.value.size > 20 * 1024 * 1024) {
    ElMessage.error('文件大小超过 20MB 限制')
    return
  }
  uploading.value = true
  uploadPct.value = 0
  try {
    await uploadDocument(uploadFile.value, uploadKbId.value, (pct) => (uploadPct.value = pct))
    ElMessage.success('上传成功, 正在解析与向量化')
    uploadVisible.value = false
    load()
  } finally {
    uploading.value = false
  }
}

function resetUpload() {
  uploadFile.value = null
  uploadKbId.value = null
  uploadPct.value = 0
}

async function onReingest(row: DocumentItem) {
  await reingestDocument(row.id)
  ElMessage.success('已触发重新向量化')
  load()
}

async function onDelete(id: number) {
  await deleteDocument(id)
  ElMessage.success('已删除')
  load()
}

onMounted(async () => {
  kbList.value = await listEnabledKb()
  kbMap.value = Object.fromEntries(kbList.value.map((k) => [k.id, k.name]))
  const q = route.query.knowledgeBaseId
  if (q) filterKb.value = Number(q)
  load()
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 18px;
}
.head-actions {
  display: flex;
  gap: 10px;
}
.pager {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}
</style>
