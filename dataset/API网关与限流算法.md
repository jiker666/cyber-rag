# API 网关与限流算法实践

## 为什么需要 API 网关

微服务与前后端分离架构下, 网关统一承担横切关注点:

1. 统一接入与路由(对外一个入口)
2. 认证鉴权(校验 JWT 后转发用户身份)
3. 限流熔断(保护后端)
4. 日志审计与监控埋点
5. 请求/响应改写(脱敏、裁剪)

## 限流算法对比

### 固定窗口计数

每分钟一个计数器, 超限拒绝。实现简单, 但窗口边界有突刺问题(两窗口交界可放过 2 倍流量)。

### 滑动窗口

将窗口切分为小格子滚动统计, 平滑了边界问题, 内存开销略高。

### 漏桶

请求进入桶中, 以固定速率流出处理; 桶满即拒绝。输出速率绝对平滑, 适合保护脆弱下游, 但无法应对合理突发。

### 令牌桶(最常用)

```
以速率 r 向桶中放令牌(容量 b), 请求取到令牌才放行
```

允许受控突发(攒下的令牌), 兼顾保护与弹性, 适合绝大多数 API 场景。

## 分布式限流实现

单机限流在多实例部署下失效, 需集中式计数。常用 Redis + Lua 保证原子性:

```lua
-- 令牌桶 Lua 核心(原子执行)
local rate = tonumber(ARGV[1])        -- 令牌生成速率/秒
local capacity = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local key = KEYS[1]

local bucket = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(bucket[1]) or capacity
local ts = tonumber(bucket[2]) or now

tokens = math.min(capacity, tokens + (now - ts) * rate)
local allowed = 0
if tokens >= 1 then
  tokens = tokens - 1
  allowed = 1
end
redis.call('HMSET', key, 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', key, 60)
return allowed
```

## 分层限流策略

| 层级 | 维度 | 示例阈值 |
|------|------|---------|
| 网关全局 | 总 QPS | 10000/s |
| 接口级 | URL 维度 | 1000/s |
| 用户级 | userId | 100 次/分钟 |
| IP 级 | 源 IP | 300 次/分钟(防匿名滥用) |
| 敏感接口 | 登录/验证码 | 5 次/分钟 |

超限响应: `429 Too Many Requests` + `Retry-After` 头, 客户端可退避重试。

## 熔断与降级

- 熔断器三态: 关闭(正常) → 打开(错误率超阈值, 快速失败) → 半开(放行探测)
- 降级: 后端不可用时返回缓存/兜底文案, 保住核心链路
- 隔离: 线程池/信号量按下游隔离, 一个慢下游不拖垮全部

## 实践清单

- 登录、验证码、找回密码等接口必须有用户级+IP 级双重限流
- 限流阈值基于压测容量设定, 预留安全余量
- 429 响应不泄露内部结构
- 限流命中计入监控, 突增本身就是攻击信号
