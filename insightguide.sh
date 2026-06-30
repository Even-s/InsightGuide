#!/bin/bash
# InsightGuide app-style launcher.

set -e

export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

FRONTEND_URL="http://localhost:5174"
BACKEND_URL="http://localhost:8002"
API_DOCS_URL="http://localhost:8002/docs"
DOCKER_COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"

bold() {
    printf "\033[1m%s\033[0m\n" "$1"
}

info() {
    printf "   %s\n" "$1"
}

http_ok() {
    curl -s -m 2 "$1" >/dev/null 2>&1
}

compose() {
    if command -v docker-compose >/dev/null 2>&1; then
        docker-compose -f "$DOCKER_COMPOSE_FILE" "$@"
    else
        docker compose "$@"
    fi
}

open_url() {
    local url="${1:-$FRONTEND_URL}"

    if command -v open >/dev/null 2>&1; then
        open "$url"
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$url" >/dev/null 2>&1 &
    else
        info "Open this URL in your browser: $url"
    fi
}

wait_for_http() {
    local name="$1"
    local url="$2"
    local attempts="${3:-20}"

    for _ in $(seq 1 "$attempts"); do
        if http_ok "$url"; then
            info "✅ $name is ready"
            return 0
        fi
        sleep 1
    done
}

print_header() {
    echo ""
    bold "InsightGuide"
    echo "Local app control center"
    echo "Frontend: $FRONTEND_URL"
    echo "Backend:  $BACKEND_URL"
    echo ""
}

quick_status() {
    local backend_state="down"
    local frontend_state="down"
    local docker_state="down"

    if http_ok "$BACKEND_URL/health"; then
        backend_state="ready"
    fi

    if http_ok "$FRONTEND_URL"; then
        frontend_state="ready"
    fi

    if command -v docker >/dev/null 2>&1 && docker ps --filter "name=insightguide" --format "{{.Names}}" 2>/dev/null | grep -q "insightguide"; then
        docker_state="running"
    fi

    printf "   Backend:  %s\n" "$backend_state"
    printf "   Frontend: %s\n" "$frontend_state"
    printf "   Docker:   %s\n" "$docker_state"
}

start_app() {
    print_header
    bold "Checking InsightGuide..."
    quick_status
    echo ""

    if http_ok "$BACKEND_URL/health" && http_ok "$FRONTEND_URL"; then
        bold "InsightGuide is already running."
    else
        bold "Starting InsightGuide services..."
        "$ROOT_DIR/bin/restart-all.sh"
    fi

    if [ "$1" = "--open" ]; then
        echo ""
        bold "Opening InsightGuide..."
        open_url "$FRONTEND_URL"
    fi
}

restart_app() {
    print_header
    bold "Restarting InsightGuide services..."
    "$ROOT_DIR/bin/restart-all.sh"

    if [ "$1" = "--open" ]; then
        echo ""
        bold "Opening InsightGuide..."
        open_url "$FRONTEND_URL"
    fi
}

stop_app() {
    print_header
    bold "Stopping InsightGuide services..."
    "$ROOT_DIR/bin/stop-services.sh"
}

restart_backend() {
    bold "Restarting Backend..."
    info "Stopping old backend process..."
    pkill -f "uvicorn app.main:app.*--port 8002" 2>/dev/null || true
    lsof -ti:8002 | xargs kill -9 2>/dev/null || true
    sleep 1

    info "Starting new backend process..."
    cd "$ROOT_DIR/backend"
    source venv/bin/activate
    nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload > "$ROOT_DIR/logs/backend.log" 2>&1 &
    echo $! > "$ROOT_DIR/logs/backend.pid"
    cd "$ROOT_DIR"

    wait_for_http "Backend" "$BACKEND_URL/health"
    bold "Backend restart complete."
}

restart_frontend() {
    bold "Restarting Frontend..."
    info "Stopping old frontend process..."
    pkill -f "frontend/node_modules/.bin/vite" 2>/dev/null || true
    lsof -ti:5174 | xargs kill -9 2>/dev/null || true
    sleep 1

    info "Starting new frontend process..."
    cd "$ROOT_DIR/frontend"
    nohup npm run dev > "$ROOT_DIR/logs/frontend.log" 2>&1 &
    echo $! > "$ROOT_DIR/logs/frontend.pid"
    cd "$ROOT_DIR"

    wait_for_http "Frontend" "$FRONTEND_URL"
    bold "Frontend restart complete."
}

restart_service() {
    case "$1" in
        backend) restart_backend ;;
        frontend) restart_frontend ;;
        *) restart_app ;;
    esac
}

show_status() {
    print_header
    "$ROOT_DIR/bin/status.sh"
}

show_logs() {
    print_header
    bold "Recent logs"

    mkdir -p logs
    for log_name in backend celery frontend; do
        local log_file="logs/${log_name}.log"
        echo ""
        bold "$log_name"
        if [ -f "$log_file" ]; then
            tail -40 "$log_file"
        else
            info "No log file yet: $log_file"
        fi
    done
}

tail_logs() {
    print_header
    bold "Following logs. Press Ctrl-C to stop."
    mkdir -p logs
    touch logs/backend.log logs/celery.log logs/frontend.log
    tail -f logs/backend.log logs/celery.log logs/frontend.log
}

doctor() {
    print_header
    bold "Environment check"

    for cmd in docker curl npm; do
        if command -v "$cmd" >/dev/null 2>&1; then
            info "$cmd: ok ($(command -v "$cmd"))"
        else
            info "$cmd: missing"
        fi
    done

    if [ -d backend/venv ]; then
        info "backend/venv: ok"
    else
        info "backend/venv: missing"
    fi

    if [ -d frontend/node_modules ]; then
        info "frontend/node_modules: ok"
    else
        info "frontend/node_modules: missing"
    fi

    echo ""
    bold "Docker compose services"
    if command -v docker >/dev/null 2>&1; then
        compose -f docker-compose.yml ps 2>/dev/null || info "Docker compose is not ready."
    else
        info "Docker is not installed or not on PATH."
    fi
}

interactive_menu() {
    while true; do
        print_header
        quick_status
        echo ""
        echo "1. Launch and open"
        echo "2. Restart and open"
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
            1) start_app --open ;;
            2) restart_app --open ;;
            3) open_url "$FRONTEND_URL" ;;
            4) show_status ;;
            5) show_logs ;;
            6) tail_logs ;;
            7) stop_app ;;
            8) doctor ;;
            9) exit 0 ;;
            *) echo "Unknown action: $choice" ;;
        esac

        echo ""
        printf "Press Enter to return to InsightGuide control center..."
        read -r _
    done
}

usage() {
    cat <<EOF
InsightGuide app-style launcher

Usage:
  ./insightguide.sh                 Open the interactive control center
  ./insightguide.sh launch          Start services if needed, then open InsightGuide
  ./insightguide.sh start           Start services if needed
  ./insightguide.sh restart [all|backend|frontend]
  ./insightguide.sh stop            Stop all services
  ./insightguide.sh status          Show detailed service status
  ./insightguide.sh open            Open InsightGuide in the browser
  ./insightguide.sh docs            Open FastAPI docs
  ./insightguide.sh logs            Show recent backend/celery/frontend logs
  ./insightguide.sh tail            Follow backend/celery/frontend logs
  ./insightguide.sh doctor          Check local dependencies
EOF
}

case "${1:-menu}" in
    menu) interactive_menu ;;
    launch) start_app --open ;;
    start) start_app ;;
    restart) restart_service "${2:-all}" ;;
    stop) stop_app ;;
    status) show_status ;;
    open) open_url "$FRONTEND_URL" ;;
    docs) open_url "$API_DOCS_URL" ;;
    logs) show_logs ;;
    tail) tail_logs ;;
    doctor) doctor ;;
    help|--help|-h) usage ;;
    *)
        usage
        exit 1
        ;;
esac
