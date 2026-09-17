import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
    { path: '/register', name: 'register', component: () => import('@/views/RegisterView.vue'), meta: { public: true } },
    {
      path: '/',
      component: () => import('@/layouts/BasicLayout.vue'),
      redirect: '/dashboard',
      children: [
        { path: 'dashboard', name: 'dashboard', component: () => import('@/views/DashboardView.vue'), meta: { title: '数据看板' } },
        { path: 'chat', name: 'chat', component: () => import('@/views/ChatView.vue'), meta: { title: '智能问答' } },
        { path: 'conversations', name: 'conversations', component: () => import('@/views/ConversationsView.vue'), meta: { title: '历史会话' } },
        { path: 'knowledge', name: 'knowledge', component: () => import('@/views/KnowledgeListView.vue'), meta: { title: '知识库' } },
        { path: 'knowledge/:id', name: 'knowledge-detail', component: () => import('@/views/KnowledgeDetailView.vue'), meta: { title: '知识库详情' } },
        { path: 'documents', name: 'documents', component: () => import('@/views/DocumentsView.vue'), meta: { title: '文档管理' } },
        { path: 'evaluation', name: 'evaluation', component: () => import('@/views/EvaluationView.vue'), meta: { title: 'RAG 实验' } },
        { path: 'settings/rag', name: 'rag-settings', component: () => import('@/views/SettingsRagView.vue'), meta: { title: 'RAG 配置', admin: true } },
        { path: 'profile', name: 'profile', component: () => import('@/views/ProfileView.vue'), meta: { title: '个人中心' } },
        { path: 'admin/users', name: 'admin-users', component: () => import('@/views/admin/UserManageView.vue'), meta: { title: '用户管理', admin: true } },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
})

router.beforeEach((to) => {
  const userStore = useUserStore()
  if (!to.meta.public && !userStore.token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.admin && !userStore.isAdmin) {
    return { name: 'dashboard' }
  }
  return true
})

export default router
