#!/bin/bash
# Stop the complete local InsightGuide stack.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

bold "停止 InsightGuide"
info "停止前端、Celery 與後端..."
stop_application_services
ok "應用程序已停止"

if command_exists docker && docker info >/dev/null 2>&1; then
    info "停止 Docker 基礎服務..."
    compose stop postgres redis minio
    ok "Docker 基礎服務已停止"
else
    warn "Docker daemon 未啟動，跳過容器停止"
fi

bold "✅ InsightGuide 已停止"
