<template>
  <div class="page">
    <h2 class="page-title">个人中心</h2>
    <p class="page-subtitle">账号信息与安全设置</p>

    <el-row :gutter="16">
      <el-col :span="9">
        <el-card shadow="never">
          <template #header><span class="card-title">基本信息</span></template>
          <div class="profile-head">
            <el-avatar :size="72" class="big-avatar">{{ userStore.nickname.slice(0, 1) }}</el-avatar>
            <div>
              <div class="p-nickname">{{ userStore.user?.nickname }}</div>
              <div class="p-username">@{{ userStore.user?.username }}</div>
              <el-tag size="small" :type="userStore.isAdmin ? 'danger' : 'info'" style="margin-top: 6px">
                {{ userStore.user?.roleName }}
              </el-tag>
            </div>
          </div>
          <el-form :model="profileForm" label-width="60px" class="profile-form">
            <el-form-item label="昵称">
              <el-input v-model="profileForm.nickname" maxlength="50" />
            </el-form-item>
            <el-form-item label="邮箱">
              <el-input v-model="profileForm.email" placeholder="选填" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="savingProfile" @click="onSaveProfile">保存</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
      <el-col :span="9">
        <el-card shadow="never">
          <template #header><span class="card-title">修改密码</span></template>
          <el-form :model="passwordForm" label-width="80px" class="profile-form">
            <el-form-item label="原密码">
              <el-input v-model="passwordForm.oldPassword" type="password" show-password />
            </el-form-item>
            <el-form-item label="新密码">
              <el-input v-model="passwordForm.newPassword" type="password" show-password placeholder="至少 6 位" />
            </el-form-item>
            <el-form-item label="确认密码">
              <el-input v-model="passwordForm.confirm" type="password" show-password />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="savingPassword" @click="onChangePassword">修改密码</el-button>
            </el-form-item>
          </el-form>
          <el-alert type="info" :closable="false" title="密码使用 BCrypt 单向哈希存储, 系统任何位置不保存明文密码" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { updateProfile, updatePassword } from '@/api/auth'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const profileForm = reactive({ nickname: '', email: '' })
const passwordForm = reactive({ oldPassword: '', newPassword: '', confirm: '' })
const savingProfile = ref(false)
const savingPassword = ref(false)

async function onSaveProfile() {
  if (!profileForm.nickname.trim()) {
    ElMessage.warning('昵称不能为空')
    return
  }
  savingProfile.value = true
  try {
    await updateProfile({ ...profileForm })
    await userStore.refreshProfile()
    ElMessage.success('已保存')
  } finally {
    savingProfile.value = false
  }
}

async function onChangePassword() {
  if (passwordForm.newPassword.length < 6) {
    ElMessage.warning('新密码至少 6 位')
    return
  }
  if (passwordForm.newPassword !== passwordForm.confirm) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  savingPassword.value = true
  try {
    await updatePassword({ oldPassword: passwordForm.oldPassword, newPassword: passwordForm.newPassword })
    ElMessage.success('密码已修改, 下次登录请使用新密码')
    passwordForm.oldPassword = ''
    passwordForm.newPassword = ''
    passwordForm.confirm = ''
  } finally {
    savingPassword.value = false
  }
}

onMounted(() => {
  profileForm.nickname = userStore.user?.nickname || ''
  profileForm.email = userStore.user?.email || ''
  userStore.refreshProfile()
})
</script>

<style scoped>
.card-title {
  font-weight: 600;
  font-size: 14px;
}
.profile-head {
  display: flex;
  align-items: center;
  gap: 18px;
  margin-bottom: 22px;
}
.big-avatar {
  background: var(--accent);
  font-size: 28px;
  font-weight: 700;
  color: #fff;
}
.p-nickname {
  font-size: 18px;
  font-weight: 600;
}
.p-username {
  color: var(--text-secondary);
  font-size: 13px;
  margin-top: 2px;
}
.profile-form {
  max-width: 360px;
}
</style>
