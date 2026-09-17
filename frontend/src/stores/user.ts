import { defineStore } from 'pinia'
import { login, register, fetchProfile, type LoginPayload, type RegisterPayload } from '@/api/auth'
import type { UserInfo } from '@/api/auth'

const TOKEN_KEY = 'cyberrag_token'
const USER_KEY = 'cyberrag_user'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    user: JSON.parse(localStorage.getItem(USER_KEY) || 'null') as UserInfo | null,
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    isAdmin: (s) => s.user?.roleCode === 'ADMIN',
    nickname: (s) => s.user?.nickname || s.user?.username || '用户',
  },
  actions: {
    setSession(token: string, user: UserInfo) {
      this.token = token
      this.user = user
      localStorage.setItem(TOKEN_KEY, token)
      localStorage.setItem(USER_KEY, JSON.stringify(user))
    },
    async doLogin(payload: LoginPayload) {
      const res = await login(payload)
      this.setSession(res.token, res.user)
    },
    async doRegister(payload: RegisterPayload) {
      const res = await register(payload)
      this.setSession(res.token, res.user)
    },
    async refreshProfile() {
      if (!this.token) return
      try {
        this.user = await fetchProfile()
        localStorage.setItem(USER_KEY, JSON.stringify(this.user))
      } catch {
        /* token 失效由拦截器处理 */
      }
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
    },
  },
})
