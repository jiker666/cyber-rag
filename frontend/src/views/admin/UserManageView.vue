<template>
  <div class="page">
    <h2 class="page-title">用户管理</h2>
    <p class="page-subtitle">系统用户与权限管理</p>

    <el-card shadow="never">
      <div class="toolbar">
        <el-input
          v-model="keyword"
          placeholder="搜索用户名/昵称"
          clearable
          style="width: 240px"
          @keyup.enter="load"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button type="primary" @click="load">查询</el-button>
      </div>

      <el-table :data="records" v-loading="loading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column label="用户" min-width="160">
          <template #default="{ row }">
            <div class="user-cell">
              <el-avatar :size="30" class="mini-avatar">{{ (row.nickname || row.username).slice(0, 1) }}</el-avatar>
              <div>
                <div>{{ row.nickname }}</div>
                <div class="sub">@{{ row.username }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" min-width="150">
          <template #default="{ row }">{{ row.email || '-' }}</template>
        </el-table-column>
        <el-table-column label="角色" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.roleCode === 'ADMIN' ? 'danger' : 'info'" size="small">{{ row.roleName }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
              {{ row.status === 1 ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最后登录" width="170">
          <template #default="{ row }">{{ formatTime(row.lastLoginAt) }}</template>
        </el-table-column>
        <el-table-column label="注册时间" width="170">
          <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              text
              :type="row.status === 1 ? 'danger' : 'success'"
              @click="onToggleStatus(row)"
            >
              {{ row.status === 1 ? '禁用' : '启用' }}
            </el-button>
            <el-button size="small" text type="primary" @click="onResetPassword(row)">重置密码</el-button>
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { pageUsers, updateUserStatus, resetUserPassword, type UserInfo } from '@/api/auth'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const records = ref<UserInfo[]>([])
const loading = ref(false)
const keyword = ref('')
const page = ref(1)
const size = 10
const total = ref(0)

function formatTime(t: string | null) {
  return t ? t.replace('T', ' ').slice(0, 19) : '-'
}

async function load() {
  loading.value = true
  try {
    const res = await pageUsers({ page: page.value, size, keyword: keyword.value || undefined })
    records.value = res.records
    total.value = res.total
  } finally {
    loading.value = false
  }
}

async function onToggleStatus(row: UserInfo) {
  await updateUserStatus(row.id, row.status === 1 ? 0 : 1)
  ElMessage.success('状态已更新')
  load()
}

async function onResetPassword(row: UserInfo) {
  const { value } = await ElMessageBox.prompt(`为用户 @${row.username} 设置新密码`, '重置密码', {
    inputPattern: /^.{6,64}$/,
    inputErrorMessage: '密码长度 6-64 位',
  })
  await resetUserPassword(row.id, value)
  ElMessage.success('密码已重置')
}

onMounted(load)
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}
.user-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}
.mini-avatar {
  background: var(--accent);
  color: #fff;
  flex-shrink: 0;
}
.sub {
  color: var(--text-secondary);
  font-size: 12px;
}
.pager {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}
</style>
