<template>
  <div class="page">
    <h2 class="page-title">历史会话</h2>
    <p class="page-subtitle">管理全部问答会话记录</p>

    <el-card shadow="never">
      <el-table :data="records" v-loading="loading">
        <el-table-column label="会话标题" min-width="220">
          <template #default="{ row }">
            <el-link type="primary" @click="openChat(row.id)">{{ row.title }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="messageCount" label="消息数" width="90" align="center" />
        <el-table-column label="关联知识库" width="140" align="center">
          <template #default="{ row }">
            <el-tag v-if="kbMap[row.knowledgeBaseId]" size="small">{{ kbMap[row.knowledgeBaseId] }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="最近消息" width="170">
          <template #default="{ row }">{{ formatTime(row.lastMessageAt) }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="openChat(row.id)">查看</el-button>
            <el-button size="small" text @click="onRename(row)">重命名</el-button>
            <el-popconfirm title="删除后不可恢复, 确认?" @confirm="onDelete(row.id)">
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
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { pageConversations, renameConversation, deleteConversation, type ConversationItem } from '@/api/chat'
import { listEnabledKb } from '@/api/kb'

const router = useRouter()
const records = ref<ConversationItem[]>([])
const loading = ref(false)
const page = ref(1)
const size = 10
const total = ref(0)
const kbMap = ref<Record<number, string>>({})

function formatTime(t: string | null) {
  return t ? t.replace('T', ' ').slice(0, 19) : '-'
}

async function load() {
  loading.value = true
  try {
    const res = await pageConversations({ page: page.value, size })
    records.value = res.records
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function openChat(id: number) {
  router.push({ path: '/chat', query: { conversationId: String(id) } })
}

async function onRename(row: ConversationItem) {
  const { value } = await ElMessageBox.prompt('会话标题', '重命名会话', {
    inputValue: row.title,
    inputPattern: /^.{1,100}$/,
    inputErrorMessage: '标题长度 1-100 字符',
  })
  await renameConversation(row.id, value)
  ElMessage.success('已重命名')
  load()
}

async function onDelete(id: number) {
  await deleteConversation(id)
  ElMessage.success('已删除')
  load()
}

onMounted(async () => {
  const kbs = await listEnabledKb()
  kbMap.value = Object.fromEntries(kbs.map((k) => [k.id, k.name]))
  load()
})
</script>

<style scoped>
.pager {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}
</style>
