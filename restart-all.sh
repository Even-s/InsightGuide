#!/bin/bash
# Restart all InsightGuide services.

set -e

export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

mkdir -p logs

echo "🔄 重啟所有 InsightGuide 服務..."
echo ""

require_cmd() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "❌ 找不到 $cmd。請確認 Docker / Node.js 已安裝，或 PATH 包含 /usr/local/bin /opt/homebrew/bin。"
        exit 1
    fi
}

compose() {
    if command -v docker-compose >/dev/null 2>&1; then
        docker-compose "$@"
    else
        docker compose "$@"
    fi
}

wait_for_http() {
    local name="$1"
    local url="$2"
    local attempts="${3:-20}"

    for _ in $(seq 1 "$attempts"); do
        if curl -s -m 3 "$url" >/dev/null 2>&1; then
            echo "   ✅ $name 啟動成功"
            return 0
        fi
        sleep 1
    done

    echo "   ❌ $name 未響應：$url"
    return 1
}

wait_for_container_health() {
    local container="$1"
    local attempts="${2:-30}"

    for _ in $(seq 1 "$attempts"); do
        local status
        status="$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container" 2>/dev/null || echo unknown)"
        if [ "$status" = "healthy" ] || [ "$status" = "running" ]; then
            echo "   ✅ $container: $status"
            return 0
        fi
        sleep 1
    done

    echo "   ❌ $container 尚未就緒"
    return 1
}

require_cmd docker
require_cmd curl
require_cmd npm

echo "1️⃣  停止現有服務..."
launchctl remove insightguide.frontend 2>/dev/null || true
launchctl remove insightguide.celery 2>/dev/null || true
pkill -9 -f "uvicorn app.main:app" 2>/dev/null || true
pkill -9 -f "celery -A app.workers.celery_app worker" 2>/dev/null || true
pkill -9 -f "Project/InsightGuide/frontend/node_modules/.bin/vite" 2>/dev/null || true
pkill -9 -f "npm run dev" 2>/dev/null || true
lsof -ti:8002 | xargs kill -9 2>/dev/null || true
lsof -ti:5174 | xargs kill -9 2>/dev/null || true
sleep 2
echo "   ✅ 已停止舊進程"
echo ""

echo "2️⃣  啟動 Docker 服務..."
compose -f docker-compose.yml up -d postgres redis minio
wait_for_container_health insightguide-postgres
wait_for_container_health insightguide-redis
wait_for_container_health insightguide-minio
echo ""

echo "3️⃣  啟動後端 (Port 8002)..."
cd "$ROOT_DIR/backend"
source venv/bin/activate
DEBUG=false nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload > "$ROOT_DIR/logs/backend.log" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$ROOT_DIR/logs/backend.pid"
cd "$ROOT_DIR"
if ! wait_for_http "後端" "http://localhost:8002/health" 20; then
    tail -40 logs/backend.log
    exit 1
fi
echo "   PID: $BACKEND_PID"
echo ""

echo "4️⃣  啟動 Celery worker..."
if command -v launchctl >/dev/null 2>&1; then
    launchctl submit -l insightguide.celery -o "$ROOT_DIR/logs/celery.log" -e "$ROOT_DIR/logs/celery.err" -- /bin/bash -lc "cd '$ROOT_DIR/backend' && source venv/bin/activate && export DEBUG=false && celery -A app.workers.celery_app worker --loglevel=info --pool=solo"
    echo "   ✅ Celery 已透過 launchctl 啟動"
else
    cd "$ROOT_DIR/backend"
    DEBUG=false nohup celery -A app.workers.celery_app worker --loglevel=info --pool=solo > "$ROOT_DIR/logs/celery.log" 2>&1 &
    CELERY_PID=$!
    echo "$CELERY_PID" > "$ROOT_DIR/logs/celery.pid"
    cd "$ROOT_DIR"
    echo "   ✅ Celery 已啟動 (PID: $CELERY_PID)"
fi
echo ""

echo "5️⃣  啟動前端 (Port 5174)..."
if command -v launchctl >/dev/null 2>&1; then
    launchctl submit -l insightguide.frontend -o "$ROOT_DIR/logs/frontend.log" -e "$ROOT_DIR/logs/frontend.err" -- /bin/bash -lc "cd '$ROOT_DIR/frontend' && export PATH='$PATH' && npm run dev"
    echo "   ✅ 前端已透過 launchctl 啟動"
else
    cd "$ROOT_DIR/frontend"
    nohup npm run dev > "$ROOT_DIR/logs/frontend.log" 2>&1 &
    FRONTEND_PID=$!
    echo "$FRONTEND_PID" > "$ROOT_DIR/logs/frontend.pid"
    cd "$ROOT_DIR"
    echo "   ✅ 前端已啟動 (PID: $FRONTEND_PID)"
fi
if ! wait_for_http "前端" "http://localhost:5174" 20; then
    tail -40 logs/frontend.log
    [ -f logs/frontend.err ] && tail -40 logs/frontend.err
    exit 1
fi
echo ""

echo "📊 服務狀態："
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -n "後端 (8002): "
curl -s -m 2 http://localhost:8002/health >/dev/null && echo "✅ 運行中" || echo "❌ 未響應"
echo -n "前端 (5174): "
curl -s -m 2 http://localhost:5174 >/dev/null && echo "✅ 運行中" || echo "❌ 未響應"
docker ps --filter "name=insightguide" --format "{{.Names}} {{.Status}}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "🌐 訪問地址："
echo "   前端: http://localhost:5174"
echo "   後端: http://localhost:8002"
echo "   API 文檔: http://localhost:8002/docs"
echo ""

echo "📝 日誌位置："
echo "   後端: logs/backend.log"
echo "   Celery: logs/celery.log"
echo "   前端: logs/frontend.log"
echo ""

echo "✅ 所有服務已重啟！"
