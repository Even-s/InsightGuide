#!/bin/bash
# Show the live state of every local InsightGuide service.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

status_line() {
    local state="$1"
    local message="$2"
    if [ "$state" = "ok" ]; then
        printf "   ✅ %s\n" "$message"
    else
        printf "   ❌ %s\n" "$message"
    fi
}

bold "InsightGuide 服務狀態"
echo ""

bold "應用程序"
if http_ok "$BACKEND_URL/health"; then
    status_line ok "後端 API：正常 ($BACKEND_URL)"
else
    status_line fail "後端 API：未回應 ($BACKEND_URL)"
fi

if celery_ok; then
    status_line ok "Celery worker：運行中"
else
    status_line fail "Celery worker：未運行"
fi

if http_ok "$FRONTEND_URL"; then
    status_line ok "前端：正常 ($FRONTEND_URL)"
else
    status_line fail "前端：未回應 ($FRONTEND_URL)"
fi
echo ""

bold "Docker 基礎服務"
if command_exists docker && docker info >/dev/null 2>&1; then
    for item in \
        "insightguide-postgres:PostgreSQL" \
        "insightguide-redis:Redis" \
        "insightguide-minio:MinIO"; do
        container="${item%%:*}"
        name="${item#*:}"
        state="$(container_state "$container")"
        if [ "$state" = "healthy" ] || [ "$state" = "running" ]; then
            status_line ok "${name}：${state}"
        else
            status_line fail "${name}：${state}"
        fi
    done
else
    status_line fail "Docker daemon：未啟動"
fi
echo ""

bold "快速連結"
echo "   前端:     $FRONTEND_URL"
echo "   後端:     $BACKEND_URL"
echo "   API 文件: $BACKEND_URL/docs"
echo "   MinIO:    http://localhost:9001"
echo ""

bold "Log"
for name in backend celery frontend; do
    log_file="$LOG_DIR/${name}.log"
    err_file="$LOG_DIR/${name}.err"
    log_size=0
    err_size=0
    [ -f "$log_file" ] && log_size="$(wc -l < "$log_file" | tr -d ' ')"
    [ -f "$err_file" ] && err_size="$(wc -l < "$err_file" | tr -d ' ')"
    printf "   %-8s %s lines, error %s lines\n" "$name" "$log_size" "$err_size"
done
