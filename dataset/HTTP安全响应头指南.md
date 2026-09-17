# HTTP 安全响应头配置指南

HTTP 安全响应头通过浏览器强制执行安全策略, 是低成本高收益的纵深防御手段。

## 核心响应头

### Strict-Transport-Security (HSTS)

强制浏览器后续访问使用 HTTPS:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

注意: 启用前确认全站 HTTPS 可用, 否则子域名将无法访问; preload 列表需谨慎加入。

### Content-Security-Policy (CSP)

限制页面可加载资源, 是 XSS 的纵深防御:

```
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'
```

- 从 report-only 模式起步, 观察违规日志后切换 enforce
- 逐步移除 `unsafe-inline`/`unsafe-eval`, 前端打包使用 nonce/hash

### X-Content-Type-Options

```
X-Content-Type-Options: nosniff
```

禁止浏览器 MIME 嗅探, 防止将非脚本文件当脚本执行。

### X-Frame-Options / frame-ancestors

```
X-Frame-Options: DENY
```

防止页面被 iframe 嵌套, 抵御点击劫持。CSP 的 `frame-ancestors 'none'` 为现代替代。

### Referrer-Policy

```
Referrer-Policy: strict-origin-when-cross-origin
```

控制 Referer 泄露范围, 避免完整 URL(含查询参数中的敏感数据)外泄。

### Permissions-Policy

```
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

禁用不必要的浏览器能力(摄像头、麦克风、定位)。

## Nginx 配置示例

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self'" always;
```

`always` 参数确保错误响应也携带这些头。

## Cookie 属性

响应头之外, Cookie 的三个安全属性同样关键:

- `Secure`: 仅 HTTPS 传输
- `HttpOnly`: 禁止 JavaScript 读取, 防 XSS 窃取会话
- `SameSite=Lax/Strict`: 限制跨站携带, 缓解 CSRF

## 验证方式

- 浏览器开发者工具逐响应检查头部
- 使用 securityheaders.com 等公开扫描器评级
- 纳入 CI 自动化检测, 防止配置回退
