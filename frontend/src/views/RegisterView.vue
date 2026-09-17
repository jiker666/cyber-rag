<template>
  <div class="auth-page">
    <div class="auth-panel">
      <div class="auth-brand">
        <el-icon :size="42" color="#d97757"><Shield /></el-icon>
        <h1>注册账号</h1>
        <p>加入 CyberRAG, 开启网络安全智能问答</p>
      </div>
      <el-form ref="formRef" :model="form" :rules="rules" size="large" @keyup.enter="onSubmit">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名(字母/数字/下划线)" :prefix-icon="User" />
        </el-form-item>
        <el-form-item prop="nickname">
          <el-input v-model="form.nickname" placeholder="昵称" :prefix-icon="Avatar" />
        </el-form-item>
        <el-form-item prop="email">
          <el-input v-model="form.email" placeholder="邮箱(选填)" :prefix-icon="Message" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="form.password" type="password" placeholder="密码(至少6位)" :prefix-icon="Lock" show-password />
        </el-form-item>
        <el-form-item prop="confirm">
          <el-input v-model="form.confirm" type="password" placeholder="确认密码" :prefix-icon="Lock" show-password />
        </el-form-item>
        <el-button class="submit-btn" type="primary" :loading="loading" @click="onSubmit">
          注 册
        </el-button>
        <div class="auth-links">
          <router-link to="/login">已有账号? 返回登录</router-link>
        </div>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, Avatar, Message } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()
const formRef = ref()
const loading = ref(false)

const form = reactive({
  username: '',
  nickname: '',
  email: '',
  password: '',
  confirm: '',
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_]{3,30}$/, message: '仅字母/数字/下划线, 3-30 位', trigger: 'blur' },
  ],
  nickname: [{ required: true, message: '请输入昵称', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度 6-64 位', trigger: 'blur' },
  ],
  confirm: [
    {
      validator: (_r: unknown, value: string, cb: (e?: Error) => void) => {
        if (value !== form.password) cb(new Error('两次密码不一致'))
        else cb()
      },
      trigger: 'blur',
    },
  ],
}

async function onSubmit() {
  await formRef.value?.validate()
  loading.value = true
  try {
    await userStore.doRegister({
      username: form.username,
      password: form.password,
      nickname: form.nickname,
      email: form.email || undefined,
    })
    ElMessage.success('注册成功, 已自动登录')
    router.push('/dashboard')
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
  padding: 36px 36px 24px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 18px;
  box-shadow: var(--shadow-card);
}
.auth-brand {
  text-align: center;
  margin-bottom: 22px;
}
.auth-brand h1 {
  margin: 10px 0 6px;
  font-size: 24px;
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
</style>
