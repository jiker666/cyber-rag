# SQL 注入攻击原理与防御指南

## 什么是 SQL 注入

SQL 注入(SQL Injection, CWE-89)是一种将恶意 SQL 语句插入应用程序查询参数, 从而欺骗后端数据库执行非预期命令的攻击方式。它长期位居 OWASP Top 10 漏洞列表前列, 可能导致数据泄露、数据篡改、认证绕过甚至服务器接管。

## 攻击原理

当应用程序将用户输入直接拼接进 SQL 语句时, 攻击者可以构造特殊输入改变语句逻辑。以登录场景为例:

```sql
-- 拼接式查询(危险)
SELECT * FROM users WHERE username = '输入1' AND password = '输入2'
```

若攻击者在用户名处输入 `admin' --`, 拼接后的语句变为:

```sql
SELECT * FROM users WHERE username = 'admin' --' AND password = '...'
```

`--` 之后的内容被注释, 密码校验被完全绕过。更严重的情况下, 攻击者可利用 `UNION SELECT` 读取任意表数据, 或利用数据库特性执行系统命令。

## 常见攻击类型

1. **基于布尔的盲注**: 通过页面返回差异逐位猜测数据。
2. **基于时间的盲注**: 利用 `SLEEP()` 等函数根据响应时间推断数据。
3. **UNION 注入**: 利用 `UNION SELECT` 合并查询结果直接读取数据。
4. **堆叠查询**: 分号后追加第二条语句(取决于数据库与驱动配置)。

## 防御措施

### 1. 参数化查询(首选)

使用预编译语句(Prepared Statement), 用户输入只作为数据绑定, 不参与 SQL 语法解析:

```java
// Java JDBC
String sql = "SELECT * FROM users WHERE username = ? AND password = ?";
PreparedStatement ps = conn.prepareStatement(sql);
ps.setString(1, username);
ps.setString(2, password);
```

### 2. 使用 ORM 框架

MyBatis 使用 `#{}` 占位符即参数化绑定; 严禁使用 `${}` 直接拼接:

```xml
<!-- 正确: 参数化 -->
<select id="findUser">SELECT * FROM users WHERE id = #{id}</select>
<!-- 危险: 字符串拼接, 存在注入风险 -->
<select id="bad">SELECT * FROM users ORDER BY ${column}</select>
```

### 3. 输入校验

对输入进行白名单校验(类型、长度、格式、字符集), 例如 ID 参数只允许数字。

### 4. 最小权限原则

数据库账号仅授予业务所需最小权限, 禁止应用账号使用 root 或 sa 权限。

### 5. 其他加固

- 错误信息脱敏, 避免暴露数据库结构与驱动信息
- 部署 WAF 作为辅助防线
- 定期代码审计与漏洞扫描

## Spring Boot 中的安全实践

Spring Boot 项目推荐统一使用 Spring Data JPA、MyBatis 的参数化能力; 对动态排序字段等无法参数化的场景, 使用白名单映射:

```java
private static final Map<String, String> ORDER_WHITE_LIST = Map.of(
    "createTime", "created_at",
    "username", "username"
);
String column = ORDER_WHITE_LIST.getOrDefault(requestColumn, "created_at");
```
