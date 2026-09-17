# 反序列化漏洞与 Java 安全

## 什么是反序列化漏洞

反序列化(CWE-502)漏洞发生在应用对不可信数据调用反序列化接口时。攻击者构造恶意序列化数据, 触发目标类中的危险逻辑(如 `readObject` 中的代码执行), 最终实现远程代码执行。

## Java 原生序列化风险

Java 的 `ObjectInputStream.readObject()` 会自动执行对象图中的钩子方法(`readObject`、`readResolve`、`hashCode` 等)。当 classpath 中存在"反序列化小工具链"(gadget chain)时, 恶意对象可在反序列化瞬间触发任意命令。

典型案例:

- **Apache Commons-Collections**: Transformer 链实现任意命令执行, 2015 年起大规模利用
- **Fastjson**: JSON 反序列化 + `@type` 自动类加载, 配合 JNDI 注入实现 RCE
- **Log4j2 JNDI**: 虽非典型反序列化, 同属"不可信数据触发组件危险行为"家族

## 防御措施

1. **避免对不可信数据使用原生序列化**: 优先使用 JSON(如 Jackson 显式绑定 DTO, 禁用默认类型推断)
2. **白名单类过滤**: JEP 290 序列化过滤器, 限定可反序列化的类

```java
ObjectInputFilter filter = ObjectInputFilter.Config.createFilter(
    "com.example.model.*;java.lang.*;!*");
ois.setObjectInputFilter(filter);
```

3. **升级组件**: 及时升级存在 gadget 的库, 关注 CVE 公告
4. **最小化攻击面**: 移除不必要依赖, classpath 越大风险越高
5. **网络隔离**: RMI、JMX、Dubbo 等反序列化高危端口不对公网暴露

## Jackson/Fastjson 安全配置

```java
// Jackson: 禁用多态类型推导
objectMapper.activateDefaultTyping(LaissezFaireSubTypeValidator.instance,
        ObjectMapper.DefaultTyping.NON_FINAL); // 危险示例, 勿用!
// 安全做法: 只绑定到具体 DTO, 不开启 default typing
MyDto dto = objectMapper.readValue(json, MyDto.class);
```

Fastjson: 升级到 safeMode(禁用 autoType)版本, 或迁移 Jackson/Gson。

## 通用原则

- 反序列化应被视为"代码执行"而非"数据解析"
- 任何接收外部序列化对象的接口都需要鉴权与输入限制
- 在 RAG 等文档处理场景中, 解析不可信文档使用成熟解析库并开启严格模式, 解析失败即拒绝
