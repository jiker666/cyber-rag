<template>
  <el-container class="layout">
    <el-aside :width="collapsed ? '64px' : '220px'" class="sidebar">
      <div class="logo" @click="router.push('/dashboard')">
        <el-icon :size="26" color="#d97757"><Shield /></el-icon>
        <transition name="fade">
          <span v-if="!collapsed" class="logo-text">CyberRAG</span>
        </transition>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="collapsed"
        router
        class="sidebar-menu"
      >
        <el-menu-item index="/dashboard">
          <el-icon><DataBoard /></el-icon>
          <template #title>数据看板</template>
        </el-menu-item>
        <el-menu-item index="/chat">
          <el-icon><ChatDotRound /></el-icon>
          <template #title>智能问答</template>
        </el-menu-item>
        <el-menu-item index="/conversations">
          <el-icon><Clock /></el-icon>
          <template #title>历史会话</template>
        </el-menu-item>
        <el-menu-item index="/knowledge">
          <el-icon><Collection /></el-icon>
          <template #title>知识库</template>
        </el-menu-item>
        <el-menu-item v-if="userStore.isAdmin" index="/documents">
          <el-icon><FolderOpened /></el-icon>
          <template #title>文档管理</template>
        </el-menu-item>
        <el-menu-item index="/evaluation">
          <el-icon><DataAnalysis /></el-icon>
          <template #title>RAG 实验</template>
        </el-menu-item>
        <el-menu-item v-if="userStore.isAdmin" index="/settings/rag">
          <el-icon><Setting /></el-icon>
          <template #title>RAG 配置</template>
        </el-menu-item>
        <el-menu-item v-if="userStore.isAdmin" index="/admin/users">
          <el-icon><UserFilled /></el-icon>
          <template #title>用户管理</template>
        </el-menu-item>
      </el-menu>
      <div class="sidebar-footer">
        <el-icon class="collapse-btn" @click="collapsed = !collapsed">
          <Expand v-if="collapsed" />
          <Fold v-else />
        </el-icon>
      </div>
    </el-aside>

    <el-container>
      <el-header class="topbar" height="56px">
        <div class="topbar-title">{{ route.meta.title || 'CyberRAG' }}</div>
        <div class="topbar-right">
          <el-tag v-if="aiOnline === true" type="success" size="small" effect="plain" round>
            <el-icon><CircleCheck /></el-icon> AI 服务在线
          </el-tag>
          <el-tag v-else-if="aiOnline === false" type="danger" size="small" effect="plain" round>
            AI 服务离线
          </el-tag>
          <el-dropdown @command="onCommand">
            <span class="user-entry">
              <el-avatar :size="30" class="avatar">{{ userStore.nickname.slice(0, 1) }}</el-avatar>
              <span class="username">{{ userStore.nickname }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">
                  <el-icon><User /></el-icon>个人中心
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import request from '@/api/request'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const collapsed = ref(false)
const aiOnline = ref<boolean | null>(null)

const activeMenu = computed(() => {
  if (route.path.startsWith('/knowledge')) return '/knowledge'
  return route.path
})

onMounted(async () => {
  userStore.refreshProfile()
  try {
    await request.get('/rag-config/runtime')
    aiOnline.value = true
  } catch {
    aiOnline.value = false
  }
})

function onCommand(cmd: string) {
  if (cmd === 'logout') {
    userStore.logout()
    router.push('/login')
  } else if (cmd === 'profile') {
    router.push('/profile')
  }
}
</script>

<style scoped>
.layout {
  height: 100%;
}
.sidebar {
  background: var(--bg-panel);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  transition: width 0.2s;
  overflow: hidden;
}
.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 16px 14px;
  cursor: pointer;
  white-space: nowrap;
}
.logo-text {
  font-family: var(--font-serif);
  font-size: 19px;
  font-weight: 700;
  letter-spacing: 0.4px;
  color: var(--text-primary);
}
.sidebar-menu {
  border-right: none;
  flex: 1;
  padding: 4px;
}
.sidebar-menu :deep(.el-menu-item) {
  border-radius: 9px;
  margin: 2px 8px;
  height: 42px;
  color: var(--text-primary);
}
.sidebar-menu :deep(.el-menu-item:hover) {
  background: var(--bg-hover);
}
.sidebar-menu :deep(.el-menu-item.is-active) {
  background: var(--accent-soft);
  color: var(--accent-strong);
}
.sidebar-menu :deep(.el-menu-item.is-active .el-icon) {
  color: var(--accent-strong);
}
.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--border-color);
}
.collapse-btn {
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 18px;
}
.collapse-btn:hover {
  color: var(--accent-strong);
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
  padding: 0 22px;
}
.topbar-title {
  font-family: var(--font-serif);
  font-size: 17px;
  font-weight: 600;
}
.topbar-right {
  display: flex;
  align-items: center;
  gap: 14px;
}
.user-entry {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: var(--text-primary);
}
.avatar {
  background: var(--accent);
  color: #fff;
  font-weight: 600;
}
.username {
  font-size: 13px;
}
.main {
  background: var(--bg-base);
  padding: 0;
  overflow-y: auto;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}
</style>
