# CSRF 跨站请求伪造防御指南

## 什么是 CSRF

跨站请求伪造(Cross-Site Request Forgery, CWE-352)是指攻击者诱导已登录用户的浏览器, 在用户不知情的情况下向目标站点发送恶意请求。由于请求携带了用户的合法会话凭证(如 Cookie), 服务器难以区分这是否为用户本人意愿, 从而以用户身份执行了操作。

## 攻击原理与示例

用户已登录 `bank.example`, 会话 Cookie 仍然有效。攻击者在第三方页面埋入:

```html
<img src="https://bank.example/transfer?to=attacker&amount=10000">
```

用户访问该页面时, 浏览器自动携带 Cookie 发起转账请求, 攻击完成。

关键条件:

1. 受害者在目标站点持有有效会话
2. 目标操作仅需 Cookie 即可认证, 无二次确认
3. 攻击者能诱导受害者访问恶意页面

## 防御措施

### 1. CSRF Token(主流方案)

服务器为每个会话生成随机 Token, 嵌入表单或请求头; 请求到达时校验 Token 是否匹配。攻击者无法跨站读取该 Token, 伪造请求即告失败。

```html
<form method="post" action="/transfer">
  <input type="hidden" name="_csrf" value="随机Token">
  ...
</form>
```

Spring Security 默认启用 CsrfFilter, 对非幂等请求(POST/PUT/DELETE)校验 `_csrf` 参数或 `X-CSRF-TOKEN` 头。

### 2. SameSite Cookie

现代浏览器支持 SameSite 属性, 限制 Cookie 在跨站请求中发送:

```
Set-Cookie: SESSIONID=xxx; SameSite=Lax; Secure; HttpOnly
```

- `Strict`: 完全不跨站发送
- `Lax`: 导航级 GET 请求允许携带(浏览器默认)

### 3. 校验 Origin 与 Referer

对敏感请求检查 `Origin`/`Referer` 头是否为本站域名, 拒绝来源不明的跨站请求。

### 4. 避免 GET 产生副作用

严格遵守 HTTP 语义: 查询用 GET, 修改用 POST/PUT/DELETE, 从根源上杜绝 img/script 标签型 CSRF。

### 5. 二次认证

对转账、改密、删除等高危操作要求再次输入密码、验证码或动态口令。

## CSRF 与 XSS 的区别

- CSRF 利用服务器对浏览器的信任, 攻击的是"用户身份"; XSS 利用站点对输出的信任, 攻击的是"浏览器执行环境"。
- XSS 通常可以用来绕过 CSRF Token 防御(脚本可读取 Token), 因此修复 XSS 是 CSRF 防御的前置条件。

## 前后端分离项目的注意事项

纯 Token(如 JWT 存于 localStorage 并通过 Authorization 头传递)方案天然免疫经典 CSRF, 因为跨站表单无法携带自定义头。但若将 Token 同时放入 Cookie, 则仍需结合 SameSite 与 CSRF Token 防御。
