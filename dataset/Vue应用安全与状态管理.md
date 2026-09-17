# Vue 应用安全与状态管理实践

## Vue 的安全模型

Vue 模板插值 `{{ }}` 默认对内容进行 HTML 转义, 这使得常规 XSS 难以直接生效。风险点集中在刻意绕过转义的 API:

- `v-html`: 直接渲染原始 HTML
- 动态组件/属性绑定传入不受信内容
- 与后端拼接的 URL 直接跳转

## v-html 使用规范

仅用于服务端可信富文本(如管理员发布的内容), 且渲染前必须净化:

```javascript
import DOMPurify from 'dompurify'

const safeHtml = computed(() =>
  DOMPurify.sanitize(props.html, {
    ALLOWED_TAGS: ['p', 'b', 'i', 'a', 'ul', 'ol', 'li', 'code', 'pre'],
    ALLOWED_ATTR: ['href', 'class']
  })
)
```

对 LLM 生成的 Markdown/HTML 同样适用: 输出渲染前净化, 链接校验协议(禁 `javascript:`)。

## 状态管理(Pinia)安全要点

1. **Token 存储**: 建议内存(Pinia store)+ 持久化到 sessionStorage/localStorage 的权衡

```typescript
// stores/auth.ts
export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  function setToken(t: string) {
    token.value = t
    localStorage.setItem('token', t)  // 需配合短有效期 + XSS 防御
  }
  function logout() {
    token.value = null
    localStorage.removeItem('token')
  }
  return { token, setToken, logout }
})
```

2. store 中不放密码、API Key 等长期敏感数据
3. 路由守卫只做体验跳转, 真正权限在服务端
4. 退出登录清理所有本地状态与缓存数据

## 请求层安全

- axios 拦截器统一注入 Token, 响应 401 统一登出
- 不在前端 axios 代码中硬编码任何第三方 API Key(前端可被提取)
- 上传文件前校验大小与类型(体验层), 服务端重复校验(安全层)

```typescript
request.interceptors.request.use(cfg => {
  const auth = useAuthStore()
  if (auth.token) cfg.headers.Authorization = `Bearer ${auth.token}`
  return cfg
})
```

## 构建与依赖

- lockfile 入库, `npm audit` 纳入 CI
- 生产构建关闭 sourcemap 上传公开渠道
- 第三方 SDK 按需引入, 锁定版本
