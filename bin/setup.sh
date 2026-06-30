#!/bin/bash
# InsightGuide - First-time setup script.
# Installs all dependencies and configures the environment.

set -e

export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

bold() { printf "\033[1m%s\033[0m\n" "$1"; }
info() { printf "   %s\n" "$1"; }
fail() { printf "   ❌ %s\n" "$1"; exit 1; }

bold "InsightGuide 首次安裝"
echo ""

# ─── Check prerequisites ───────────────────────────────────────────────────────

bold "1. 檢查前置需求..."

MISSING=""

if ! command -v docker >/dev/null 2>&1; then
    MISSING="${MISSING}\n   ❌ docker — 請安裝 Docker Desktop：https://www.docker.com/products/docker-desktop/"
fi

if ! command -v node >/dev/null 2>&1; then
    MISSING="${MISSING}\n   ❌ node — 請安裝 Node.js 20+：brew install node 或 https://nodejs.org/"
elif [ "$(node -v | cut -d. -f1 | tr -d 'v')" -lt 20 ]; then
    MISSING="${MISSING}\n   ❌ node 版本過舊 ($(node -v)) — 需要 20+：brew upgrade node"
fi

if ! command -v python3 >/dev/null 2>&1; then
    MISSING="${MISSING}\n   ❌ python3 — 請安裝 Python 3.11+：brew install python@3.11 或 https://www.python.org/"
fi

if [ -n "$MISSING" ]; then
    echo ""
    bold "缺少以下工具，請先安裝："
    printf "$MISSING\n"
    echo ""
    info "macOS 一鍵安裝所有前置需求："
    info "  brew install --cask docker && brew install node python@3.11"
    echo ""
    info "安裝完成後請重新執行：./insightguide.sh setup"
    exit 1
fi

info "✅ docker: $(docker --version | head -1)"
info "✅ node: $(node -v)"
info "✅ python3: $(python3 --version)"
echo ""

# ─── Environment file ─────────────────────────────────────────────────────────

bold "2. 配置環境..."

if [ ! -f backend/.env ]; then
    cp backend/.env.example backend/.env
    info "已建立 backend/.env（請填入 OPENAI_API_KEY）"
else
    info "backend/.env 已存在，跳過"
fi
echo ""

# ─── Docker services ──────────────────────────────────────────────────────────

bold "3. 啟動 Docker 基礎服務 (PostgreSQL, Redis, MinIO)..."

compose() {
    if command -v docker-compose >/dev/null 2>&1; then
        docker-compose "$@"
    else
        docker compose "$@"
    fi
}

compose -f docker-compose.yml up -d postgres redis minio

wait_for_container() {
    local container="$1"
    local attempts=30
    for _ in $(seq 1 "$attempts"); do
        local status
        status="$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container" 2>/dev/null || echo unknown)"
        if [ "$status" = "healthy" ] || [ "$status" = "running" ]; then
            info "✅ $container: $status"
            return 0
        fi
        sleep 1
    done
    fail "$container 啟動失敗"
}

wait_for_container insightguide-postgres
wait_for_container insightguide-redis
wait_for_container insightguide-minio
echo ""

# ─── Backend setup ────────────────────────────────────────────────────────────

bold "4. 安裝後端依賴..."

cd "$ROOT_DIR/backend"

if [ ! -d venv ]; then
    python3 -m venv venv
    info "已建立 Python 虛擬環境"
fi

source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
info "✅ Python 依賴安裝完成"
echo ""

bold "5. 執行資料庫 migrations..."
alembic upgrade head
info "✅ 資料庫 schema 已就緒"
echo ""

cd "$ROOT_DIR"

# ─── Frontend setup ───────────────────────────────────────────────────────────

bold "6. 安裝前端依賴..."

cd "$ROOT_DIR/frontend"
npm install --silent
info "✅ 前端依賴安裝完成"
echo ""

cd "$ROOT_DIR"

# ─── Make scripts executable ──────────────────────────────────────────────────

chmod +x insightguide.sh InsightGuide.command bin/*.sh

# ─── Done ─────────────────────────────────────────────────────────────────────

bold "✅ 安裝完成！"
echo ""
echo "下一步："
echo "  1. 編輯 backend/.env，填入你的 OPENAI_API_KEY"
echo "  2. 執行 ./insightguide.sh launch 啟動系統"
echo ""
