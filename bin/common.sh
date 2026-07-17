#!/bin/bash
# Shared runtime helpers for InsightGuide service scripts.

export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"

BACKEND_PORT=8002
FRONTEND_PORT=5174
BACKEND_URL="http://localhost:${BACKEND_PORT}"
FRONTEND_URL="http://localhost:${FRONTEND_PORT}"

mkdir -p "$LOG_DIR"

bold() { printf "\033[1m%s\033[0m\n" "$1"; }
info() { printf "   %s\n" "$1"; }
ok() { printf "   ✅ %s\n" "$1"; }
warn() { printf "   ⚠️  %s\n" "$1"; }
fail() { printf "   ❌ %s\n" "$1" >&2; return 1; }

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

http_ok() {
    curl -fsS -m 3 "$1" >/dev/null 2>&1
}

compose() {
    if command_exists docker-compose; then
        docker-compose -f "$COMPOSE_FILE" "$@"
    else
        docker compose -f "$COMPOSE_FILE" "$@"
    fi
}

wait_for_http() {
    local name="$1"
    local url="$2"
    local attempts="${3:-30}"

    for _ in $(seq 1 "$attempts"); do
        if http_ok "$url"; then
            ok "$name 已就緒"
            return 0
        fi
        sleep 1
    done

    fail "$name 未回應：$url"
}

wait_for_docker() {
    if ! command_exists docker; then
        fail "找不到 Docker，請先安裝 Docker Desktop"
        return 1
    fi

    if docker info >/dev/null 2>&1; then
        return 0
    fi

    if [ "$(uname -s)" = "Darwin" ] && [ -d /Applications/Docker.app ]; then
        info "Docker Desktop 尚未啟動，正在開啟..."
        open -a Docker
    else
        fail "Docker daemon 未啟動"
        return 1
    fi

    for _ in $(seq 1 60); do
        if docker info >/dev/null 2>&1; then
            ok "Docker Desktop 已就緒"
            return 0
        fi
        sleep 2
    done

    fail "Docker Desktop 在 120 秒內未就緒"
}

container_state() {
    docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$1" 2>/dev/null || echo missing
}

wait_for_container() {
    local container="$1"
    local attempts="${2:-30}"
    local state

    for _ in $(seq 1 "$attempts"); do
        state="$(container_state "$container")"
        if [ "$state" = "healthy" ] || [ "$state" = "running" ]; then
            ok "$container: $state"
            return 0
        fi
        sleep 1
    done

    fail "$container 未就緒（目前狀態：$(container_state "$container")）"
}

service_label() {
    printf "insightguide.%s" "$1"
}

service_is_managed() {
    local name="$1"
    local label
    label="$(service_label "$name")"

    if command_exists launchctl; then
        launchctl list "$label" >/dev/null 2>&1
    else
        local pid_file="$LOG_DIR/${name}.pid"
        [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file" 2>/dev/null)" 2>/dev/null
    fi
}

start_service() {
    local name="$1"
    local working_dir="$2"
    local command="$3"
    local label
    label="$(service_label "$name")"

    # A fresh service run should have a fresh diagnostic surface.
    : > "$LOG_DIR/${name}.log"
    : > "$LOG_DIR/${name}.err"

    if command_exists launchctl; then
        launchctl remove "$label" >/dev/null 2>&1 || true
        launchctl submit -l "$label" \
            -o "$LOG_DIR/${name}.log" \
            -e "$LOG_DIR/${name}.err" \
            -- /bin/bash -lc "cd '$working_dir' && exec $command"
        printf "launchctl:%s\n" "$label" > "$LOG_DIR/${name}.pid"
    else
        (
            cd "$working_dir" || exit 1
            nohup /bin/bash -lc "exec $command" > "$LOG_DIR/${name}.log" 2> "$LOG_DIR/${name}.err" &
            echo "$!" > "$LOG_DIR/${name}.pid"
        )
    fi
}

stop_service() {
    local name="$1"
    local label
    local pid_file="$LOG_DIR/${name}.pid"
    label="$(service_label "$name")"

    if command_exists launchctl; then
        launchctl remove "$label" >/dev/null 2>&1 || true
        for _ in $(seq 1 20); do
            if ! launchctl list "$label" >/dev/null 2>&1; then
                break
            fi
            sleep 0.1
        done
    fi

    if [ -f "$pid_file" ]; then
        local pid_value
        pid_value="$(cat "$pid_file" 2>/dev/null)"
        case "$pid_value" in
            ''|launchctl:*) ;;
            *) kill "$pid_value" >/dev/null 2>&1 || true ;;
        esac
        rm -f "$pid_file"
    fi

    case "$name" in
        backend) wait_for_port_release "$BACKEND_PORT" ;;
        frontend) wait_for_port_release "$FRONTEND_PORT" ;;
        celery) wait_for_process_release "celery -A app.workers.celery_app worker" ;;
    esac
}

kill_listening_port_tree() {
    local port="$1"
    local signal="${2:-TERM}"
    local pids

    pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u || true)"
    [ -z "$pids" ] && return 0

    for pid in $pids; do
        local ppid
        local parent_command
        ppid="$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')"
        parent_command="$(ps -o command= -p "$ppid" 2>/dev/null || true)"

        kill "-$signal" "$pid" >/dev/null 2>&1 || true

        # Vite and uvicorn --reload keep a parent watcher that can respawn the
        # port-listening child. Only stop that parent when it is the known local
        # dev watcher for this application.
        case "$parent_command" in
            *"npm run dev"*|*"uvicorn app.main:app"*)
                kill "-$signal" "$ppid" >/dev/null 2>&1 || true
                ;;
        esac
    done
}

wait_for_port_release() {
    local port="$1"
    for _ in $(seq 1 30); do
        if ! lsof -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
            return 0
        fi
        sleep 0.1
    done

    kill_listening_port_tree "$port" TERM
    sleep 0.5

    if lsof -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
        kill_listening_port_tree "$port" KILL
        sleep 0.5
    fi
}

wait_for_process_release() {
    local pattern="$1"
    for _ in $(seq 1 30); do
        if ! pgrep -f "$pattern" >/dev/null 2>&1; then
            return 0
        fi
        sleep 0.1
    done
}

stop_application_services() {
    stop_service frontend
    stop_service celery
    stop_service backend

    # Clean up processes left by older launch scripts.
    kill_listening_port_tree "$BACKEND_PORT" TERM
    kill_listening_port_tree "$FRONTEND_PORT" TERM
    pkill -f "$ROOT_DIR/backend/venv/bin/python.*celery -A app.workers.celery_app worker" >/dev/null 2>&1 || true
    wait_for_port_release "$BACKEND_PORT"
    wait_for_port_release "$FRONTEND_PORT"
    wait_for_process_release "$ROOT_DIR/backend/venv/bin/python.*celery -A app.workers.celery_app worker"
}

celery_ok() {
    service_is_managed celery && pgrep -f "celery -A app.workers.celery_app worker" >/dev/null 2>&1
}

wait_for_celery() {
    local attempts="${1:-15}"
    for _ in $(seq 1 "$attempts"); do
        if celery_ok; then
            ok "Celery 已就緒"
            return 0
        fi
        sleep 1
    done
    fail "Celery worker 未就緒"
}
