<template>
  <div class="page">
    <h2 class="page-title">RAG 参数配置</h2>
    <p class="page-subtitle">检索增强问答核心参数, 修改后立即生效于后续问答与实验</p>

    <el-row :gutter="16">
      <el-col :span="14">
        <el-card shadow="never">
          <template #header><span class="card-title">检索与生成参数</span></template>
          <el-form :model="config" label-width="150px" v-if="config" :disabled="saving">
            <el-form-item label="Chunk Size">
              <el-input-number v-model="config.chunkSize" :min="64" :max="4096" :step="64" />
              <span class="hint">文档切片长度(字符)</span>
            </el-form-item>
            <el-form-item label="Chunk Overlap">
              <el-input-number v-model="config.chunkOverlap" :min="0" :max="4000" :step="10" />
              <span class="hint">相邻切片重叠字符数</span>
            </el-form-item>
            <el-form-item label="检索策略">
              <el-select v-model="config.retrievalStrategy" style="width: 180px">
                <el-option label="向量检索" value="vector" />
                <el-option label="混合检索(向量+BM25)" value="hybrid" />
              </el-select>
              <span class="hint">hybrid 用 RRF 融合精确词召回</span>
            </el-form-item>
            <el-form-item label="Top-K">
              <el-input-number v-model="config.topK" :min="1" :max="50" />
              <span class="hint">检索返回知识片段数</span>
            </el-form-item>
            <el-form-item label="Temperature">
              <el-input-number v-model="config.temperature" :min="0" :max="2" :step="0.1" />
              <span class="hint">LLM 生成随机度</span>
            </el-form-item>
            <el-form-item label="相似度阈值">
              <el-input-number v-model="config.scoreThreshold" :min="0" :max="1" :step="0.05" />
              <span class="hint">低于该相似度的片段被过滤</span>
            </el-form-item>
            <el-form-item label="启用 Reranker">
              <el-switch v-model="rerankerEnabled" />
              <span class="hint">交叉编码器重排序(需下载模型)</span>
            </el-form-item>
            <el-form-item v-if="rerankerEnabled" label="重排保留数量">
              <el-input-number v-model="config.rerankTopN" :min="1" :max="20" />
            </el-form-item>
            <el-form-item label="历史消息窗口">
              <el-input-number v-model="config.historyWindow" :min="0" :max="20" />
              <span class="hint">多轮对话携带的历史条数</span>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="saving" @click="onSave">保存配置</el-button>
              <el-button @click="load">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="never">
          <template #header><span class="card-title">AI 服务运行时信息</span></template>
          <div v-if="runtime" class="runtime">
            <div class="rt-row">
              <span class="rt-label">Embedding 模型</span>
              <span class="rt-value">{{ runtime.embedding.provider }} · {{ runtime.embedding.model }}</span>
            </div>
            <div class="rt-row">
              <span class="rt-label">向量维度</span>
              <span class="rt-value">{{ runtime.embedding.dimension ?? '-' }}</span>
            </div>
            <div class="rt-row">
              <span class="rt-label">LLM 模型</span>
              <span class="rt-value">{{ runtime.llm.model }}<el-tag v-if="runtime.llm.error" size="small" type="danger" style="margin-left:8px">未配置</el-tag></span>
            </div>
            <div class="rt-row">
              <span class="rt-label">Reranker</span>
              <span class="rt-value">
                {{ runtime.reranker.enabled ? runtime.reranker.model : '未启用' }}
              </span>
            </div>
            <div class="rt-row">
              <span class="rt-label">向量数据库</span>
              <span class="rt-value">{{ runtime.vectorStore.type }} (Chroma)</span>
            </div>
          </div>
          <el-alert
            type="info"
            :closable="false"
            title="LLM / Embedding 模型通过环境变量 LLM_* 与 EMBEDDING_* 配置, 密钥不落库、不回传前端"
            style="margin-top: 14px"
          />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchRagConfig, updateRagConfig, fetchRuntimeInfo, type RagConfig, type RuntimeInfo } from '@/api/config'

const config = ref<RagConfig | null>(null)
const runtime = ref<RuntimeInfo | null>(null)
const saving = ref(false)

const rerankerEnabled = computed({
  get: () => config.value?.enableReranker === 1,
  set: (v: boolean) => {
    if (config.value) config.value.enableReranker = v ? 1 : 0
  },
})

async function load() {
  config.value = await fetchRagConfig()
}

async function onSave() {
  if (!config.value) return
  saving.value = true
  try {
    config.value = await updateRagConfig({ ...config.value })
    ElMessage.success('配置已保存')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  load()
  try {
    runtime.value = await fetchRuntimeInfo()
  } catch {
    runtime.value = null
  }
})
</script>

<style scoped>
.card-title {
  font-weight: 600;
  font-size: 14px;
}
.hint {
  margin-left: 10px;
  color: var(--text-secondary);
  font-size: 12px;
}
.runtime {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.rt-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  border-bottom: 1px dashed var(--border-color);
  padding-bottom: 10px;
}
.rt-label {
  color: var(--text-secondary);
}
.rt-value {
  font-family: 'JetBrains Mono', Menlo, monospace;
  color: var(--accent-strong);
  max-width: 260px;
  word-break: break-all;
  text-align: right;
}
</style>
