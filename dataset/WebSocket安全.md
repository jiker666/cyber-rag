# WebSocket 与实时通信安全

## WebSocket 的安全模型差异

WebSocket(HTTP Upgrade 建立)建立后是长连接双向通信, 与 HTTP 的安全模型差异:

1. **浏览器同源策略不覆盖 WebSocket 握手后的帧**: 初始握手有 Origin 校验, 之后通信不受同源策略保护
2. **鉴权一次性**: 握手时的认证不代表连接期间身份始终有效(账号被封禁后连接仍在)
3. **长生命周期**: 连接数是稀缺资源, 易被连接耗尽攻击
4. **跨站 WebSocket 劫持(CSWSH)**: 浏览器自动附带 Cookie 发起握手, 恶意页面可借用受害者会话建立连接

## 关键防护

### 1. 握手阶段校验 Origin

```javascript
// 服务端(Node 示例)
const wss = new WebSocketServer({ port: 8080, verifyClient: (info) => {
  const allowed = ['https://app.example.com'];
  return allowed.includes(info.origin);   // 必须精确匹配
}});
```

### 2. 不要依赖 Cookie 自动认证

握手请求带 `Authorization` 头或一次性票据:

```
GET /ws HTTP/1.1
Upgrade: websocket
Authorization: Bearer <jwt>
```

或 URL 携带短时效一次性 ticket, 避免使用长效 Cookie(防 CSWSH)。

### 3. 连接生命周期管理

- 心跳检测, 超时断开僵尸连接
- 单用户连接数上限(防单账号耗尽资源)
- 服务端可主动踢下线: 权限变更/封禁时立即断开
- 优雅关闭: 会话结束时清理服务端订阅与内存

### 4. 消息层安全

- 对消息内容校验与限制(最大帧长度、频率限制), 防止应用层 DoS
- 消息格式用二进制协议或 JSON + schema 校验, 拒绝畸形消息
- 敏感数据仍需应用层加密(若 TLS 终止在代理, 代理到后端的链路也要保护)
- 防注入: 消息若渲染到 DOM, 走 XSS 输出编码

## 反向代理配置

```
# Nginx WebSocket 代理
location /ws {
    proxy_pass http://app;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 300s;    # 长读超时, 防误断
    proxy_limit_rate 512k;      # 带宽限制
}
```

## 与 SSE/长轮询的选择

- **WebSocket**: 高频双向(协作编辑、游戏、IM)
- **SSE**: 服务端单向推送(通知、日志流), 复用 HTTP 生态更简单
- **长轮询**: 兼容性兜底, 效率最低

安全本质上都要回答: 谁能建立连接、连接多久、消息可信吗。
