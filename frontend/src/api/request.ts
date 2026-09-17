import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const request = axios.create({
  baseURL: '/api',
  timeout: 300000,
})

request.interceptors.request.use((config) => {
  const token = localStorage.getItem('cyberrag_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  (response) => {
    const body = response.data
    // 后端统一 Result 结构: code=0 成功
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code !== 0) {
        ElMessage.error(body.message || '请求失败')
        return Promise.reject(new Error(body.message || '请求失败'))
      }
      return body.data
    }
    return body
  },
  (error) => {
    if (error.response) {
      const { status, data } = error.response
      if (status === 401) {
        localStorage.removeItem('cyberrag_token')
        localStorage.removeItem('cyberrag_user')
        if (router.currentRoute.value.name !== 'login') {
          ElMessage.error(data?.message || '登录已过期, 请重新登录')
          router.push({ name: 'login' })
        }
      } else {
        ElMessage.error(data?.message || `请求错误 (${status})`)
      }
    } else {
      ElMessage.error('网络异常, 请检查服务是否启动')
    }
    return Promise.reject(error)
  },
)

export default request
