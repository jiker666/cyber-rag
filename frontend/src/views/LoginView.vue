<template>
  <div class="auth-page">
    <div class="auth-panel">
      <div class="auth-brand">
        <el-icon :size="42" color="#d97757"><Shield /></el-icon>
        <h1>CyberRAG</h1>
        <p>基于 RAG 的网络安全知识智能问答平台</p>
      </div>
      <el-form ref="formRef" :model="form" :rules="rules" size="large" @keyup.enter="onSubmit">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" :prefix-icon="User" autocomplete="username" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            :prefix-icon="Lock"
            show-password
            autocomplete="current-password"
          />
        </el-form-item>
        <el-button class="submit-btn" type="primary" :loading="loading" @click="onSubmit">
          登 录
        </el-button>
        <div class="auth-links">
          <router-link to="/register">没有账号? 注册新用户</router-link>
        </div>
      </el-form>
      <el-alert type="info" :closable="false" class="demo-tip">
        <template #title>演示账号: admin / admin123(管理员), user / user123(普通用户)</template>
      </el-alert>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const formRef = ref()
const loading = ref(false)

const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function onSubmit() {
  await formRef.value?.validate()
  loading.value = true
  try {
    await userStore.doLogin({ ...form })
    ElMessage.success('登录成功')
    router.push((route.query.redirect as string) || '/dashboard')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(1100px 560px at 82% -8%, rgba(217, 119, 87, 0.09), transparent),
    radial-gradient(900px 500px at 8% 108%, rgba(192, 138, 30, 0.07), transparent),
    var(--bg-base);
}
.auth-panel {
  width: 400px;
  padding: 40px 36px 28px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 18px;
  box-shadow: var(--shadow-card);
}
.auth-brand {
  text-align: center;
  margin-bottom: 26px;
}
.auth-brand h1 {
  margin: 10px 0 6px;
  font-size: 30px;
  font-family: var(--font-serif);
  font-weight: 700;
  color: var(--text-primary);
}
.auth-brand p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
}
.submit-btn {
  width: 100%;
  margin-top: 4px;
  height: 42px;
  font-size: 15px;
}
.auth-links {
  margin-top: 14px;
  text-align: center;
  font-size: 13px;
}
.auth-links a {
  color: var(--accent);
  text-decoration: none;
}
.demo-tip {
  margin-top: 18px;
}
</style>
