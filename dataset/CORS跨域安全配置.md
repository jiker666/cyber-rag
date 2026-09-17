# CORS 跨域资源共享安全配置

## 什么是 CORS

CORS(Cross-Origin Resource Sharing)是浏览器的跨域访问控制机制。协议、域名、端口任一不同即跨域, 默认被同源策略拦截。服务端通过 CORS 响应头显式声明允许哪些来源跨域访问。

## 预检请求

非简单请求(如带 Authorization 头的 JSON 请求)会先发送 OPTIONS 预检:

```
OPTIONS /api/data HTTP/1.1
Origin: https://app.example.com
Access-Control-Request-Method: POST
Access-Control-Request-Headers: authorization, content-type
```

服务端需正确响应 `Access-Control-Allow-Origin/Methods/Headers` 与 `Access-Control-Max-Age`, 预检通过后浏览器才发送真实请求。

## 危险配置

```
Access-Control-Allow-Origin: *              # 通配符
Access-Control-Allow-Origin: https://app.example.com
Access-Control-Allow-Credentials: true      # 两者组合=灾难
```

规范禁止 `*` 与凭证共存, 于是部分实现"反射 Origin"来绕过, 这等于对任意来源放行且允许携带 Cookie, 造成大规模数据泄露。

另一类问题: `Access-Control-Allow-Origin` 反射任意 Origin 且未校验白名单 —— 攻击者站点可直接以受害者身份读取 API 数据。

## 安全实践

1. **精确白名单**: 只允许已知前端域名

```java
@Configuration
public class CorsConfig implements WebMvcConfigurer {
    private static final List<String> ALLOWED = List.of(
        "https://app.example.com", "http://localhost:5173");

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
            .allowedOrigins(ALLOWED.toArray(new String[0]))
            .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
            .allowedHeaders("*")
            .allowCredentials(true)
            .maxAge(3600);
    }
}
```

2. **禁止反射 Origin**: 校验通过才回显, 否则不返回 CORS 头
3. **最小暴露**: `Access-Control-Expose-Headers` 只声明必要的头
4. **内网服务不应对公网开放 CORS**: 内部 API 直接拒绝跨域
5. **本地开发**: 使用 Vite/Webpack devServer 代理转发(同源), 避免放宽生产 CORS 配置

## 常见排错

- 前端报 "Response to preflight request didn't pass access control check": 检查 OPTIONS 是否被鉴权拦截器挡住(需放行 OPTIONS 或在预检前返回 CORS 头)
- Nginx 与应用重复添加 CORS 头导致 `Access-Control-Allow-Origin` 出现两次: 只在一层配置
- Cookie 跨域失效: 需前后端同站部署或使用正确的 SameSite/Domain 策略
