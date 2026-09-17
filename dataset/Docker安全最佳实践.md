# Docker 安全与镜像最佳实践

## Docker 架构面的安全风险

1. **Docker Socket 泄露**: 挂载 `/var/run/docker.sock` 的容器等于拥有宿主机 root 权限, 任何 RCE 都能逃逸
2. **privileged 容器**: 关闭隔离, 等同宿主机管理员
3. **镜像投毒**: 使用不可信镜像源或被篡改的基础镜像
4. **敏感信息泄露**: Dockerfile 中 ENV 硬编码密钥, 随镜像分发
5. **容器逃逸**: 内核漏洞(CVE-2019-5736 runc、Dirty COW 等)与错误配置叠加

## 镜像构建最佳实践

```dockerfile
# 1. 固定基础镜像版本, 优先精简镜像
FROM python:3.11-slim

# 2. 不以 root 运行
RUN groupadd -r app && useradd -r -g app app

# 3. 依赖单独层缓存, 安装后清理
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && rm -rf /root/.cache

# 4. 最小复制范围, 精确路径
COPY --chown=app:app app/ /app/

# 5. 敏感配置运行时注入, 不写入镜像
# (ENV 中不得出现任何密钥/口令)

USER app
HEALTHCHECK --interval=30s CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 运行时加固

```bash
docker run -d \
  --read-only \                      # 只读根文件系统(需可写的目录用 tmpfs)
  --tmpfs /tmp \
  --cap-drop=ALL --cap-add=NET_BIND_SERVICE \  # 裁剪 capabilities
  --security-opt=no-new-privileges \ # 禁止提权
  --memory=512m --cpus=0.5 \          # 资源限制
  --pids-limit=100 \
  --user 1000:1000 \
  myapp:1.0.0
```

## 镜像供应链

- 使用内容寻址(`@sha256:...`)或签名镜像
- 私有仓库走 HTTPS + 访问控制, 定期扫描镜像 CVE
- 构建环境最小权限, CI 凭证不落盘
- 多阶段构建: 编译工具链不进入运行镜像

## Docker Compose 安全要点

```yaml
services:
  app:
    image: myapp:1.0.0
    env_file: .env            # 密钥来自 env_file, 不写进 yml
    ports:
      - "127.0.0.1:8080:8080" # 只绑定本地, 公网经反代暴露
    volumes:
      - ./data:/app/data      # 只挂载必要目录
    security_opt:
      - no-new-privileges:true
```

- compose 文件中的环境变量引用 `${VAR}` 从部署机环境读取, 密钥不入库
- 数据库容器不映射端口到公网, 内部网络通信
- 健康检查 + 重启策略保证可用性

## 监控与审计

- 审计 docker daemon 日志与容器事件
- 定期 `docker scout`/trivy 扫描运行镜像
- 关注运行中容器的异常进程、异常外联(可对接 runtime 安全组件)
