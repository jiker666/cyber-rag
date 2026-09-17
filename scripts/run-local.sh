#!/usr/bin/env bash
# 本机开发环境一键启动: rag-service(8000) + backend(8080) + frontend(5173)
set -euo pipefail
cd "$(dirname "$0")/.."

GREEN='\033[0;32m'; NC='\033[0m'
info() { echo -e "${GREEN}[INFO]${NC} $1"; }

if [ ! -f .env ]; then
    echo "[ERROR] 缺少 .env, 请先执行 ./scripts/init.sh"; exit 1
fi

PIDS=()
cleanup() {
    echo ""
    info "正在停止所有服务..."
    for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
    wait 2>/dev/null || true
    exit 0
}
trap cleanup INT TERM

# 1. RAG 服务
info "启动 RAG 服务 (FastAPI :8000)..."
(cd rag-service && [ -d .venv ] || python3 -m venv .venv)
(cd rag-service && .venv/bin/pip install -q -r requirements.txt)
(cd rag-service && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000) &
PIDS+=($!)

# 2. 后端(Spring 不读 .env, 需导出环境变量; rag-service 由 pydantic 自行读取)
info "启动后端服务 (Spring Boot :8080)..."
set -a
source .env
set +a
JAVA_HOME_21="$(brew --prefix openjdk@21 2>/dev/null || true)"
if [ -n "$JAVA_HOME_21" ] && [ -d "$JAVA_HOME_21" ]; then
    export JAVA_HOME="$JAVA_HOME_21"
    export PATH="$JAVA_HOME/bin:$PATH"
fi
(cd backend && mvn -q spring-boot:run) &
PIDS+=($!)

# 3. 前端
info "启动前端服务 (Vite :5173)..."
(cd frontend && [ -d node_modules ] || npm install)
(cd frontend && npm run dev) &
PIDS+=($!)

info "全部服务已启动:"
echo "  前端:    http://localhost:5173"
echo "  后端:    http://localhost:8080/api"
echo "  RAG服务: http://localhost:8000/health"
echo "按 Ctrl+C 停止全部服务"
wait
