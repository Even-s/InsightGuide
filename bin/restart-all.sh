#!/bin/bash
# Start or restart the complete local InsightGuide stack.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

MODE="${1:-restart}"
if [ "$MODE" != "start" ] && [ "$MODE" != "restart" ]; then
    echo "Usage: $0 [start|restart]" >&2
    exit 2
fi

check_environment() {
    local missing=0

    [ -x "$ROOT_DIR/backend/venv/bin/python" ] || { fail "backend/venv 尚未建立"; missing=1; }
    [ -x "$ROOT_DIR/backend/venv/bin/celery" ] || { fail "Celery 尚未安裝"; missing=1; }
    [ -f "$ROOT_DIR/backend/.env" ] || { fail "backend/.env 不存在"; missing=1; }
    [ -d "$ROOT_DIR/frontend/node_modules" ] || { fail "frontend/node_modules 尚未安裝"; missing=1; }
    command_exists npm || { fail "找不到 npm"; missing=1; }
    command_exists curl || { fail "找不到 curl"; missing=1; }

    if [ "$missing" -ne 0 ]; then
        info "請先執行 ./insightguide.sh setup"
        return 1
    fi
}

bold "InsightGuide ${MODE}"
echo ""

check_environment
wait_for_docker

if [ "$MODE" = "restart" ]; then
    info "停止現有應用程序..."
    stop_application_services
    sleep 1
fi

bold "1. 啟動基礎服務"
compose up -d postgres redis minio
wait_for_container insightguide-postgres
wait_for_container insightguide-redis
wait_for_container insightguide-minio
echo ""

bold "2. 更新資料庫 schema"
run_migrations
echo ""

bold "3. 啟動後端 API"
if [ "$MODE" = "start" ] && http_ok "$BACKEND_URL/health"; then
    ok "後端已在運行"
else
    stop_service backend
    start_service backend "$ROOT_DIR/backend" \
        "env DEBUG=false venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT --reload"
    if ! wait_for_http "後端" "$BACKEND_URL/health" 30; then
        tail -40 "$LOG_DIR/backend.log" 2>/dev/null || true
        tail -40 "$LOG_DIR/backend.err" 2>/dev/null || true
        exit 1
    fi
fi
echo ""

bold "4. 啟動 Celery worker"
if [ "$MODE" = "start" ] && celery_ok; then
    ok "Celery 已在運行"
else
    stop_service celery
    start_service celery "$ROOT_DIR/backend" \
        "env DEBUG=false venv/bin/celery -A app.workers.celery_app worker --loglevel=info --pool=solo"
    if ! wait_for_celery 15; then
        tail -40 "$LOG_DIR/celery.err" 2>/dev/null || true
        exit 1
    fi
fi
echo ""

bold "5. 啟動前端"
if [ "$MODE" = "start" ] && http_ok "$FRONTEND_URL"; then
    ok "前端已在運行"
else
    stop_service frontend
    start_service frontend "$ROOT_DIR/frontend" "npm run dev"
    if ! wait_for_http "前端" "$FRONTEND_URL" 30; then
        tail -40 "$LOG_DIR/frontend.log" 2>/dev/null || true
        tail -40 "$LOG_DIR/frontend.err" 2>/dev/null || true
        exit 1
    fi
fi
echo ""

bold "✅ InsightGuide 已就緒"
echo "   前端:     $FRONTEND_URL"
echo "   後端:     $BACKEND_URL"
echo "   API 文件: $BACKEND_URL/docs"
echo "   MinIO:    http://localhost:9001"
