<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2 class="page-title">网络安全知识库</h2>
        <p class="page-subtitle" style="margin-bottom: 0">领域知识库与知识片段统计</p>
      </div>
      <div class="head-actions">
        <el-input
          v-model="keyword"
          placeholder="搜索知识库"
          clearable
          style="width: 220px"
          @keyup.enter="load"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button v-if="userStore.isAdmin" type="primary" @click="dialogVisible = true">
          <el-icon><Plus /></el-icon>&nbsp;创建知识库
        </el-button>
      </div>
    </div>

    <el-row :gutter="16" class="kb-grid">
      <el-col v-for="kb in records" :key="kb.id" :xs="24" :sm="12" :md="8" :lg="6">
        <el-card shadow="hover" class="kb-card" @click="router.push(`/knowledge/${kb.id}`)">
          <div class="kb-color" :style="{ background: kb.coverColor || '#d97757' }"></div>
          <div class="kb-body">
            <div class="kb-title-row">
              <span class="kb-name">{{ kb.name }}</span>
              <el-tag v-if="kb.status === 1" size="small" type="success">启用</el-tag>
              <el-tag v-else size="small" type="info">停用</el-tag>
            </div>
            <div class="kb-desc">{{ kb.description || '暂无简介' }}</div>
            <div class="kb-meta">
              <el-tag size="small" effect="plain">{{ kb.category || '未分类' }}</el-tag>
            </div>
            <div class="kb-stats">
              <div class="kb-stat">
                <div class="num">{{ kb.docCount }}</div>
                <div class="lbl">文档</div>
              </div>
              <div class="kb-stat">
                <div class="num">{{ kb.chunkCount }}</div>
                <div class="lbl">知识片段</div>
              </div>
              <el-button
                v-if="userStore.isAdmin"
                size="small"
                text
                type="primary"
                class="sync-btn"
                @click.stop="onSync(kb)"
              >同步统计</el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    <el-empty v-if="!records.length && !loading" description="暂无知识库" />

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        :page-size="size"
        :total="total"
        layout="prev, pager, next, total"
        @current-change="load"
      />
    </div>

    <!-- 创建知识库 -->
    <el-dialog v-model="dialogVisible" title="创建知识库" width="480px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="如: Web安全知识库" maxlength="100" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="form.category" placeholder="选择分类" style="width: 100%">
            <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="简介">
          <el-input v-model="form.description" type="textarea" :rows="3" maxlength="500" />
        </el-form-item>
        <el-form-item label="封面颜色">
          <el-color-picker v-model="form.coverColor" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="onCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { pageKb, createKb, refreshKb, type KnowledgeBase } from '@/api/kb'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()
const records = ref<KnowledgeBase[]>([])
const loading = ref(false)
const keyword = ref('')
const page = ref(1)
const size = 12
const total = ref(0)
const dialogVisible = ref(false)
const creating = ref(false)

const categories = ['Web安全', 'Java安全', 'API安全', 'OWASP', 'CWE', '认证授权', '安全编码', '其他']
const form = reactive({ name: '', category: 'Web安全', description: '', coverColor: '#d97757' })

async function load() {
  loading.value = true
  try {
    const res = await pageKb({ page: page.value, size, keyword: keyword.value || undefined })
    records.value = res.records
    total.value = res.total
  } finally {
    loading.value = false
  }
}

async function onCreate() {
  if (!form.name.trim()) {
    ElMessage.warning('请输入知识库名称')
    return
  }
  creating.value = true
  try {
    await createKb({ ...form })
    ElMessage.success('创建成功')
    dialogVisible.value = false
    form.name = ''
    form.description = ''
    load()
  } finally {
    creating.value = false
  }
}

async function onSync(kb: KnowledgeBase) {
  await refreshKb(kb.id)
  ElMessage.success('已从向量库同步统计')
  load()
}

onMounted(load)
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
.kb-grid {
  margin: 0 -8px;
}
.kb-card {
  margin-bottom: 16px;
  cursor: pointer;
  overflow: hidden;
  position: relative;
  transition: transform 0.15s;
}
.kb-card:hover {
  transform: translateY(-3px);
}
.kb-color {
  height: 4px;
  border-radius: 4px 4px 0 0;
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
}
.kb-body {
  padding-top: 8px;
}
.kb-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.kb-name {
  font-size: 15px;
  font-weight: 600;
}
.kb-desc {
  color: var(--text-secondary);
  font-size: 12.5px;
  margin: 8px 0;
  min-height: 36px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.kb-meta {
  margin-bottom: 10px;
}
.kb-stats {
  display: flex;
  align-items: center;
  gap: 24px;
  border-top: 1px solid var(--border-color);
  padding-top: 10px;
}
.kb-stat .num {
  font-size: 18px;
  font-weight: 700;
  font-family: 'JetBrains Mono', Menlo, monospace;
  color: var(--accent);
}
.kb-stat .lbl {
  font-size: 11.5px;
  color: var(--text-secondary);
}
.sync-btn {
  margin-left: auto;
}
.pager {
  display: flex;
  justify-content: center;
  margin-top: 10px;
}
</style>
