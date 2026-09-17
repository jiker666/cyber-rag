#!/usr/bin/env bash
# 一键初始化: 检查环境 → 准备配置 → 初始化数据库
set -euo pipefail
cd "$(dirname "$0")/.."

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# 1. 检查 .env
if [ ! -f .env ]; then
    cp .env.example .env
    warn "已从 .env.example 生成 .env, 请编辑填入 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL 等配置"
else
    info ".env 已存在"
fi

# 2. 必填项检查(密钥只检查是否为空, 不打印内容)
missing=0
for var in LLM_BASE_URL LLM_API_KEY LLM_MODEL; do
    val=$(grep -E "^${var}=" .env | head -1 | cut -d= -f2- | tr -d '"' | tr -d ' ')
    if [ -z "$val" ] || [[ "$val" == *your-* ]]; then
        warn ".env 中 ${var} 未配置"
        missing=1
    fi
done
[ $missing -eq 1 ] && warn "LLM 配置不完整, RAG 问答将无法生成回答(仅影响生成, 不影响其他模块)"

# 3. MySQL 初始化(本机部署方式)
if command -v mysql >/dev/null 2>&1; then
    info "检测到 mysql 客户端, 开始初始化数据库..."
    MYSQL_ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-root}"
    if mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" -e "USE cyber_rag;" >/dev/null 2>&1; then
        warn "数据库 cyber_rag 已存在, 跳过初始化(如需重建请手动 DROP)"
    else
        mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" -e "CREATE DATABASE IF NOT EXISTS cyber_rag DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" cyber_rag < sql/init.sql
        info "数据库 cyber_rag 初始化完成(含演示账号 admin/admin123, user/user123)"
    fi
else
    warn "未检测到 mysql 客户端, 跳过数据库初始化(可使用 docker compose 方式自动初始化)"
fi

# 4. 后端依赖
info "初始化完成。启动方式:"
echo "  方式一(本机): ./scripts/run-local.sh"
echo "  方式二(Docker): docker compose up -d --build"
