#!/bin/bash
# InsightGuide local development control center.

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=bin/common.sh
source "$ROOT_DIR/bin/common.sh"
cd "$ROOT_DIR"

open_url() {
    local url="${1:-$FRONTEND_URL}"
    if command_exists open; then
        open "$url"
    elif command_exists xdg-open; then
        xdg-open "$url" >/dev/null 2>&1 &
    else
        info "請在瀏覽器開啟：$url"
    fi
}

print_header() {
    echo ""
    bold "InsightGuide"
    echo "Local development control center"
    echo ""
}

quick_status() {
    local backend_state="down"
    local frontend_state="down"
    local celery_state="down"
    http_ok "$BACKEND_URL/health" && backend_state="ready"
    http_ok "$FRONTEND_URL" && frontend_state="ready"
    celery_ok && celery_state="ready"
    printf "   Backend:  %s\n" "$backend_state"
    printf "   Celery:   %s\n" "$celery_state"
    printf "   Frontend: %s\n" "$frontend_state"
}

start_app() {
    "$ROOT_DIR/bin/restart-all.sh" start
}

restart_component() {
    local component="${1:-all}"

    case "$component" in
        all)
            "$ROOT_DIR/bin/restart-all.sh" restart
            ;;
        backend)
            wait_for_docker
            compose up -d postgres redis minio
            stop_service backend
            start_service backend "$ROOT_DIR/backend" \
                "env DEBUG=false venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT --reload"
            wait_for_http "後端" "$BACKEND_URL/health" 30
            ;;
        frontend)
            stop_service frontend
            start_service frontend "$ROOT_DIR/frontend" "npm run dev"
            wait_for_http "前端" "$FRONTEND_URL" 30
            ;;
        celery)
            wait_for_docker
            compose up -d redis
            stop_service celery
            start_service celery "$ROOT_DIR/backend" \
                "env DEBUG=false venv/bin/celery -A app.workers.celery_app worker --loglevel=info --pool=solo"
            wait_for_celery 15
            ;;
        *)
            echo "Unknown service: $component" >&2
            echo "Available services: all, backend, celery, frontend" >&2
            exit 2
            ;;
    esac
}

show_logs() {
    for name in backend celery frontend; do
        echo ""
        bold "$name"
        tail -40 "$LOG_DIR/${name}.log" 2>/dev/null || info "No log yet"
        if [ -s "$LOG_DIR/${name}.err" ]; then
            tail -20 "$LOG_DIR/${name}.err"
        fi
    done
}

tail_logs() {
    touch "$LOG_DIR/backend.log" "$LOG_DIR/celery.log" "$LOG_DIR/frontend.log"
    bold "Following logs. Press Ctrl-C to stop."
    tail -f "$LOG_DIR/backend.log" "$LOG_DIR/celery.log" "$LOG_DIR/frontend.log"
}

doctor() {
    print_header
    bold "Environment"
    for cmd in docker curl npm node python3; do
        if command_exists "$cmd"; then
            ok "$cmd: $(command -v "$cmd")"
        else
            fail "$cmd: missing" || true
        fi
    done
    [ -x backend/venv/bin/python ] && ok "backend/venv" || warn "backend/venv missing"
    [ -f backend/.env ] && ok "backend/.env" || warn "backend/.env missing"
    [ -d frontend/node_modules ] && ok "frontend/node_modules" || warn "frontend/node_modules missing"
    if docker info >/dev/null 2>&1; then
        ok "Docker daemon: ready"
    else
        warn "Docker daemon: not running"
    fi
}

interactive_menu() {
    while true; do
        print_header
        quick_status
        echo ""
        echo "1. Start"
        echo "2. Restart"
        echo "3. Open in browser"
        echo "4. Status"
        echo "5. Recent logs"
        echo "6. Follow logs"
        echo "7. Stop"
        echo "8. Doctor"
        echo "9. Quit"
        echo ""
        printf "Choose an action: "
        read -r choice

        case "$choice" in
            1) start_app ;;
            2) restart_component all ;;
            3) open_url ;;
            4) "$ROOT_DIR/bin/status.sh" ;;
            5) show_logs ;;
            6) tail_logs ;;
            7) "$ROOT_DIR/bin/stop-services.sh" ;;
            8) doctor ;;
            9) exit 0 ;;
            *) echo "Unknown action: $choice" ;;
        esac

        echo ""
        printf "Press Enter to continue..."
        read -r _
    done
}

usage() {
    cat <<EOF
InsightGuide local development control center

Usage:
  ./insightguide.sh                         Interactive control center
  ./insightguide.sh setup                   First-time installation
  ./insightguide.sh start                   Start all services if needed
  ./insightguide.sh launch                  Start all services and open the app
  ./insightguide.sh restart [service]       Restart all, backend, celery, or frontend
  ./insightguide.sh stop                    Stop all services
  ./insightguide.sh status                  Show live service status
  ./insightguide.sh open                    Open the frontend
  ./insightguide.sh docs                    Open FastAPI docs
  ./insightguide.sh logs                    Show recent logs
  ./insightguide.sh tail                    Follow logs
  ./insightguide.sh doctor                  Check local dependencies
EOF
}

case "${1:-menu}" in
    menu) interactive_menu ;;
    setup) "$ROOT_DIR/bin/setup.sh" ;;
    start) start_app ;;
    launch) start_app; open_url ;;
    restart) restart_component "${2:-all}" ;;
    stop) "$ROOT_DIR/bin/stop-services.sh" ;;
    status) "$ROOT_DIR/bin/status.sh" ;;
    open) open_url ;;
    docs) open_url "$BACKEND_URL/docs" ;;
    logs) show_logs ;;
    tail) tail_logs ;;
    doctor) doctor ;;
    help|--help|-h) usage ;;
    *) usage; exit 2 ;;
esac
