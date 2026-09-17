# HTTPS 与 TLS 证书机制解析

## TLS 的作用

TLS(Transport Layer Security)在传输层提供三重保障:

1. **机密性**: 对称加密保护数据不被窃听
2. **完整性**: MAC/AEAD 防止数据被篡改
3. **真实性**: 证书体系防止中间人冒充服务器

## TLS 1.3 握手简述

1. Client 发送 ClientHello(支持的密码套件、密钥共享、SNI)
2. Server 从中选定套件, 返回证书 + 签名 + 密钥共享
3. 双方基于密钥交换(ECDHE)派生会话密钥
4. (1-RTT 完成握手, TLS1.2 需 2-RTT; 0-RTT 复用需防重放)

前向保密: ECDHE 每次会话独立密钥, 私钥泄露不影响历史流量。

## 证书体系

- **证书链**: 根 CA(自签, 内置于系统/浏览器) → 中间 CA → 站点证书
- **验证内容**: 链有效、未过期、域名匹配(SAN)、未被吊销(CRL/OCSP)
- **证书类型**: DV(只验证域名)、OV(验证组织)、EV(扩展验证, 现代浏览器已淡化地址栏标识)

## 常见部署问题

1. **混合内容**: HTTPS 页面加载 HTTP 资源被浏览器拦截, 需全站升级
2. **证书链不完整**: 只部署站点证书漏掉中间证书, 部分客户端报错
3. **HSTS 配置过早**: 全站 HTTPS 未就绪就启用, 导致子域无法回退
4. **私钥权限**: 私钥文件应 root/服务账号独占读写(600)
5. **弱协议残留**: SSLv3/TLS1.0/1.1 已淘汰, 必须关闭; 优先 TLS1.2/1.3

## Nginx 推荐配置

```nginx
server {
    listen 443 ssl;
    http2 on;
    server_name example.com;

    ssl_certificate     /etc/ssl/fullchain.pem;   # 含中间证书
    ssl_certificate_key /etc/ssl/private.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    add_header Strict-Transport-Security "max-age=31536000" always;
}

server {
    listen 80;
    server_name example.com;
    return 301 https://$host$request_uri;
}
```

## 证书自动化

- Let's Encrypt 免费证书 + ACME 自动续期(certbot/cert-manager)
- 到期监控与告警, 防止证书过期事故
- 私钥轮换纳入变更管理
