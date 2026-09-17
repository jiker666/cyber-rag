# JWT 安全实践指南

## 什么是 JWT

JSON Web Token(RFC 7519)是一种无状态的认证凭证, 由三部分组成: `Header.Payload.Signature`, 以 Base64Url 编码并用点号连接。服务端通过验证签名确认 Payload 中声明的可信性, 常用于前后端分离与微服务场景下的身份认证。

- **Header**: 声明签名算法, 如 `{"alg":"HS256","typ":"JWT"}`
- **Payload**: 携带声明, 如用户 ID、角色、过期时间
- **Signature**: 对前两部分的签名, 保证完整性

## 常见安全风险

### 1. 算法混淆攻击

服务端若信任 Header 中声明的算法, 攻击者可将 `alg` 改为 `none` 或将 RS256 篡改为 HS256(用公钥当 HMAC 密钥), 伪造合法签名。防御: 服务端硬编码固定算法, 不从 Token 中读取。

### 2. 密钥强度不足与硬编码

弱密钥(如 `secret`、`123456`)可被暴力破解; 硬编码在源码中的密钥一旦泄露即全面失守。防御: 密钥仅通过环境变量或密钥管理服务注入, 长度不低于 256 位。

### 3. 敏感信息泄露

Payload 仅做 Base64 编码, 明文可读, 严禁存放密码、手机号等敏感数据。

### 4. Token 无法主动失效

JWT 无状态, 签发后在过期前始终有效。用户改密、注销或账号被盗时需要失效机制: 引入服务端黑名单(Redis)、缩短有效期配合刷新令牌、或在签名中加入版本号随密钥变更失效。

### 5. 存储位置风险

- localStorage: 易受 XSS 窃取, 需配套严格的 XSS 防御
- HttpOnly Cookie: 天然防 XSS 窃取, 但需配套 CSRF 防御

## 安全实践清单

1. 使用强随机密钥(≥32 字节), 通过环境变量配置, 不入库、不入代码仓库
2. 固定签名算法为 HS256/RS256, 服务端显式指定
3. 设置短有效期(exp, 如 2 小时)并校验 `exp`/`nbf`
4. Payload 只放必要声明(userId、role、iat、exp)
5. 每次请求均验证签名与有效期, 解析失败统一返回 401, 不区分具体错误原因
6. 注销/改密时使 Token 失效(黑名单或版本号)
7. 传输全程使用 HTTPS
8. 日志中不得打印完整 Token

## 示例: 安全的签发与校验

```java
// 签发: 密钥来自配置(环境变量注入)
SecretKey key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
String token = Jwts.builder()
    .subject(String.valueOf(userId))
    .claim("role", role)
    .issuedAt(new Date())
    .expiration(new Date(System.currentTimeMillis() + EXPIRE_MS))
    .signWith(key, Jwts.SIG.HS256)
    .compact();

// 校验: 固定算法, 异常统一处理
Claims claims = Jwts.parser().verifyWith(key).build()
    .parseSignedClaims(token).getPayload();
```
