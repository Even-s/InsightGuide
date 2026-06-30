#!/bin/bash

# InsightGuide - Status Check Script
# Check real service availability first, then use PID files as supporting detail.

export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR" || exit 1

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

BACKEND_URL="http://localhost:8002"
FRONTEND_URL="http://localhost:5174"

status_ok() {
    echo -e "${GREEN}✓${NC} $1"
}

status_warn() {
    echo -e "${YELLOW}?${NC} $1"
}

status_fail() {
    echo -e "${RED}✗${NC} $1"
}

compose() {
    if command -v docker-compose >/dev/null 2>&1; then
        docker-compose "$@"
    else
        docker compose "$@"
    fi
}

http_ok() {
    curl -s -m 3 "$1" >/dev/null 2>&1
}

pid_is_running() {
    local pid="$1"
    [ -n "$pid" ] && [[ "$pid" =~ ^[0-9]+$ ]] && ps -p "$pid" >/dev/null 2>&1
}

find_process() {
    local pattern="$1"
    pgrep -f "$pattern" 2>/dev/null | head -1
}

pid_file_note() {
    local service_name="$1"
    local pid_file="logs/${service_name}.pid"

    if [ ! -f "$pid_file" ]; then
        return 0
    fi

    local pid_value
    pid_value="$(cat "$pid_file" 2>/dev/null)"
    if [[ "$pid_value" == screen:* ]]; then
        local screen_name="${pid_value#screen:}"
        if screen -ls 2>/dev/null | grep -q "[.]${screen_name}[[:space:]]"; then
            echo "screen: $screen_name"
        else
            echo "stale screen session: $screen_name"
        fi
    elif pid_is_running "$pid_value"; then
        echo "PID: $pid_value"
    elif [ -n "$pid_value" ]; then
        echo "stale PID file: $pid_value"
    fi
}

check_web_service() {
    local service_name="$1"
    local url="$2"
    local port="$3"
    local process_pattern="$4"

    local note
    note="$(pid_file_note "$service_name")"

    if http_ok "$url"; then
        if [ -n "$note" ]; then
            status_ok "$service_name is responding ($note)"
        else
            status_ok "$service_name is responding"
        fi
        return 0
    fi

    if lsof -ti:"$port" >/dev/null 2>&1; then
        status_warn "$service_name has port $port open, but health check did not respond"
        return 1
    fi

    local process_pid
    process_pid="$(find_process "$process_pattern")"
    if [ -n "$process_pid" ]; then
        status_warn "$service_name process exists (PID: $process_pid), but port $port is not ready"
        return 1
    fi

    if [ -n "$note" ]; then
        status_fail "$service_name is not running ($note)"
    else
        status_fail "$service_name is not running"
    fi
    return 1
}

check_celery_process() {
    local note
    note="$(pid_file_note celery)"

    local process_pid
    process_pid="$(find_process "celery -A app.workers.celery_app worker")"
    if [ -n "$process_pid" ]; then
        if [ -n "$note" ]; then
            status_ok "celery process is running (PID: $process_pid; $note)"
        else
            status_ok "celery process is running (PID: $process_pid)"
        fi
        return 0
    fi

    if [ -n "$note" ]; then
        status_fail "celery process is not running ($note)"
    else
        status_fail "celery process is not running"
    fi
    return 1
}

container_running() {
    docker ps --filter "name=$1" --format "{{.Names}}" 2>/dev/null | grep -qx "$1"
}

container_health() {
    docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$1" 2>/dev/null
}

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}        InsightGuide Service Status Check${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""

echo -e "${YELLOW}📍 InsightGuide Processes:${NC}"
check_web_service "backend" "$BACKEND_URL/health" 8002 "uvicorn app.main:app.*--port 8002"
check_celery_process
check_web_service "frontend" "$FRONTEND_URL" 5174 "frontend/node_modules/.bin/vite|npm run dev"
echo ""

echo -e "${YELLOW}🔌 Port Status:${NC}"
if lsof -ti:8002 >/dev/null 2>&1; then
    status_ok "Port 8002 (Backend API) is in use"
else
    status_fail "Port 8002 (Backend API) is not in use"
fi

if lsof -ti:5174 >/dev/null 2>&1; then
    status_ok "Port 5174 (Frontend) is in use"
else
    status_fail "Port 5174 (Frontend) is not in use"
fi
echo ""

echo -e "${YELLOW}🐳 Docker Services:${NC}"
if command -v docker >/dev/null 2>&1 && compose -f docker-compose.yml ps >/dev/null 2>&1; then
    for item in "insightguide-postgres PostgreSQL (Port 5432)" "insightguide-redis Redis (Port 6379)" "insightguide-minio MinIO (Ports 9000, 9001)"; do
        container="${item%% *}"
        label="${item#* }"
        health="$(container_health "$container")"
        if container_running "$container"; then
            status_ok "$label: $health"
        else
            status_fail "$label: not running"
        fi
    done
else
    status_fail "Docker Compose services not available"
fi
echo ""

echo -e "${YELLOW}🏥 Health Checks:${NC}"
if http_ok "$BACKEND_URL/health"; then
    HEALTH="$(curl -s -m 3 "$BACKEND_URL/health")"
    BACKEND_STATUS="$(echo "$HEALTH" | jq -r '.status' 2>/dev/null || echo healthy)"
    status_ok "Backend API: $BACKEND_STATUS"
else
    status_fail "Backend API: Not responding"
fi

if docker exec insightguide-postgres sh -lc 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; then
    status_ok "PostgreSQL: Connected"
else
    status_fail "PostgreSQL: Cannot connect"
fi

if docker exec insightguide-redis redis-cli ping >/dev/null 2>&1; then
    status_ok "Redis: Connected"
else
    status_fail "Redis: Cannot connect"
fi

if http_ok "http://localhost:9000/minio/health/live"; then
    status_ok "MinIO: Healthy"
else
    status_fail "MinIO: Not responding"
fi

if http_ok "$FRONTEND_URL"; then
    status_ok "Frontend: Responding"
else
    status_warn "Frontend: Not responding (may still be starting)"
fi
echo ""

echo -e "${YELLOW}⚙️  Celery Worker Status:${NC}"
if [ -d "backend/venv" ]; then
    CELERY_INSPECT="$(
        cd backend &&
        source venv/bin/activate 2>/dev/null &&
        DEBUG=false celery -A app.workers.celery_app inspect ping 2>/dev/null
    )"
    if echo "$CELERY_INSPECT" | grep -q "pong"; then
        status_ok "Celery worker is active and responding"

        ACTIVE_TASKS="$(
            cd backend &&
            source venv/bin/activate 2>/dev/null &&
            DEBUG=false celery -A app.workers.celery_app inspect active 2>/dev/null | grep -c "id"
        )"
        if [ "${ACTIVE_TASKS:-0}" -gt 0 ]; then
            echo -e "  📋 Active tasks: $ACTIVE_TASKS"
        fi
    else
        status_fail "Celery worker not responding to ping"
    fi
else
    status_warn "Cannot activate virtualenv"
fi
echo ""

echo -e "${BLUE}📍 Service URLs:${NC}"
echo "   Frontend:       $FRONTEND_URL"
echo "   Backend API:    $BACKEND_URL"
echo "   API Docs:       $BACKEND_URL/docs"
echo "   MinIO Console:  http://localhost:9001"
echo ""

echo -e "${BLUE}📝 Recent Log Activity:${NC}"
if [ -d "logs" ]; then
    for log_name in backend celery frontend; do
        log_file="logs/${log_name}.log"
        if [ -f "$log_file" ]; then
            log_label="$log_name"
            case "$log_name" in
                backend) log_label="Backend" ;;
                celery) log_label="Celery" ;;
                frontend) log_label="Frontend" ;;
            esac
            LOG_LINES="$(wc -l < "$log_file" 2>/dev/null || echo "0")"
            printf "   %-13s %s lines\n" "$log_label log:" "$LOG_LINES"
        fi
    done
else
    echo -e "${YELLOW}   No logs directory found${NC}"
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
