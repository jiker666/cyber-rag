# Spring Boot 应用安全加固指南

## 认证与会话

### 密码存储

使用 BCrypt(自适应加盐慢哈希)存储密码, 禁止 MD5/SHA1 明文级方案:

```java
@Bean
public PasswordEncoder passwordEncoder() {
    return new BCryptPasswordEncoder(); // 默认强度 10
}
// 注册
String hash = passwordEncoder.encode(rawPassword);
// 登录校验
boolean ok = passwordEncoder.matches(rawPassword, storedHash);
```

### JWT 集成要点

- 密钥从环境变量/配置中心读取, 长度 ≥ 32 字节
- 固定签名算法, 解析异常统一 401
- Token 有效期建议 1-2 小时, 敏感操作二次校验
- 拦截器统一鉴权, 白名单(登录/注册/健康检查)显式配置

### 登录防爆破

- 失败 N 次锁定或验证码(Redis 计数)
- 统一返回"用户名或密码错误", 不提示具体哪项错误
- 登录接口限流

## 接口与授权

### 分层校验

1. 认证(是谁) → 2. 授权(能做什么) → 3. 参数校验(输入合法) → 4. 业务逻辑

### 自定义拦截器示例

```java
public class AuthInterceptor implements HandlerInterceptor {
    @Override
    public boolean preHandle(HttpServletRequest req,
                             HttpServletResponse resp, Object handler) {
        String token = req.getHeader("Authorization");
        Long userId = jwtUtil.parseAndVerify(token); // 验签+过期检查
        // @RequireAdmin 注解标记的管理接口做角色校验
        if (handler instanceof HandlerMethod hm) {
            RequireAdmin ra = hm.getMethodAnnotation(RequireAdmin.class);
            if (ra != null && !RoleEnum.ADMIN.name().equals(currentUser.getRole())) {
                throw new BusinessException(403, "无权限访问");
            }
        }
        return true;
    }
}
```

### 参数校验

Controller 层使用 `@Valid` + JSR-303 注解(`@NotBlank`、`@Size`、`@Pattern`), 全局异常处理器转换为统一错误响应, 避免 500 堆栈泄露。

## 常见配置加固

```yaml
server:
  error:
    include-stacktrace: never   # 不回显堆栈
springdoc:
  api-docs:
    enabled: false              # 生产关闭接口文档
management:
  endpoints:
    web:
      exposure:
        include: health         # Actuator 只暴露 health
```

- 关闭 Actuator 敏感端点, 网关加访问控制
- CORS 使用精确白名单, 禁用 `*`
- 依赖定期 SCA 扫描, 及时升级高危 CVE 组件

## 文件与日志

- 上传走白名单+随机名+大小限制(见文件上传安全指南)
- 日志不打印密码、Token、API Key 等敏感字段
- 记录关键审计事件: 登录成功/失败、越权尝试、管理操作

## SQL 注入防护

MyBatis 全部使用 `#{}`; 动态排序字段用白名单映射; 见 SQL 注入防护指南。
