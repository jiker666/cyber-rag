# BOLA 与 BFLA 越权漏洞深度解析

## BOLA: 对象级授权失效

### 漏洞本质

API 只验证"你是谁"(认证), 不验证"这个对象是不是你的"(授权), 导致横向越权:

```
GET /api/invoices/5001   # A 用户查看自己的发票 → 200
GET /api/invoices/5002   # A 用户查看 B 用户的发票 → 若无归属校验, 同样 200
```

BOLA 是 OWASP API Security Top 10 之首, 也是数据泄露事件的最主要根因。

### 高发场景

1. 自增整数主键暴露, 易于遍历(5001 → 5002 → ...)
2. UUID 被误认为"不可猜测即安全"(一旦泄露仍可越权)
3. 批量接口、导出接口、子资源路径(`/users/{id}/orders`)遗漏校验
4. 导航/回退接口复用了宽权限查询

### 防御实现

每次数据访问都把"归属"写进查询条件:

```java
// MyBatis-Plus: 查询条件强制带归属
Invoice invoice = invoiceMapper.selectOne(
    Wrappers.<Invoice>lambdaQuery()
        .eq(Invoice::getId, invoiceId)
        .eq(Invoice::getUserId, currentUserId));  // 关键行
if (invoice == null) {
    throw new BusinessException(404, "发票不存在"); // 统一 404, 不区分"无权/不存在"
}
```

服务端返回 404 而非 403, 避免攻击者借此确认对象存在性。

## BFLA: 功能级授权失效

### 漏洞本质

接口只做认证不做角色校验, 普通用户可调用管理功能, 造成纵向越权:

```
POST /api/admin/users/42/disable    # 普通用户调用管理接口
```

常见根因: 前端隐藏按钮但后端无校验; 管理接口与普通接口混在同一 Controller; 注解遗漏。

### 防御实现

逐接口显式声明权限, 拦截器统一执行:

```java
// 声明: 自定义注解标记管理接口
@RequireAdmin
@DeleteMapping("/api/admin/users/{id}")
public Result<Void> deleteUser(@PathVariable Long id) { ... }

// 执行: 拦截器读取注解并校验角色
RequireAdmin ra = handlerMethod.getMethodAnnotation(RequireAdmin.class);
if (ra != null && !"ADMIN".equals(AuthContext.getRole())) {
    throw new BusinessException(403, "无权限访问");
}
```

配套要求:

- 权限判断只在服务端, 前端仅做展示优化
- 管理路由独立分组(路径前缀/网关)便于统一防护
- 新增接口评审时检查授权注解, 纳入代码评审清单
- 权限默认拒绝, 显式放行

## 测试方法(授权测试环境)

1. 准备两个不同权限/不同用户身份的测试账号
2. 用户 A 正常请求资源, 记录 URL
3. 替换对象 ID 为用户 B 的资源, 观察是否返回数据(BOLA)
4. 普通用户直接调用管理接口, 观察是否执行(BFLA)
5. 结合自动化: 授权测试矩阵(用户 × 接口 × 对象)批量回归
