#!/bin/bash

# InsightGuide 快速測試腳本
# 用於快速驗證系統基本功能

set -e

BASE_URL="http://localhost:8001"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo "=========================================="
    echo "  $1"
    echo "=========================================="
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

# 測試 1: 健康檢查
print_header "測試 1: 系統健康檢查"

if curl -s "$BASE_URL/health" | grep -q "healthy"; then
    print_success "後端服務健康"
else
    print_error "後端服務異常"
    exit 1
fi

# 測試 2: Whisper API
print_header "測試 2: Whisper 轉錄 API"

LANG_COUNT=$(curl -s "$BASE_URL/api/transcription/supported-languages" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['languages']))" 2>/dev/null)

if [ "$LANG_COUNT" -gt 0 ]; then
    print_success "Whisper API 可用 (支援 $LANG_COUNT 種語言)"
else
    print_error "Whisper API 異常"
    exit 1
fi

# 測試 3: SSE 端點
print_header "測試 3: SSE 事件端點"

TEST_SESSION="test_session_$(date +%s)"
if curl -s "$BASE_URL/api/events/sessions/$TEST_SESSION/connections" | grep -q "sessionId"; then
    print_success "SSE 端點可用"
else
    print_error "SSE 端點異常"
    exit 1
fi

# 測試 4: API 文件
print_header "測試 4: API 文件"

if curl -s "$BASE_URL/docs" | grep -q "Swagger"; then
    print_success "API 文件可訪問"
    print_info "瀏覽器訪問: http://localhost:8001/docs"
else
    print_error "API 文件無法訪問"
fi

# 測試 5: Docker 服務
print_header "測試 5: Docker 容器狀態"

BACKEND_STATUS=$(docker ps --filter "name=insightguide-backend" --format "{{.Status}}" | grep -c "Up" || echo "0")
POSTGRES_STATUS=$(docker ps --filter "name=insightguide-postgres" --format "{{.Status}}" | grep -c "Up" || echo "0")
REDIS_STATUS=$(docker ps --filter "name=insightguide-redis" --format "{{.Status}}" | grep -c "Up" || echo "0")

if [ "$BACKEND_STATUS" = "1" ]; then
    print_success "Backend 容器運行中"
else
    print_error "Backend 容器未運行"
fi

if [ "$POSTGRES_STATUS" = "1" ]; then
    print_success "PostgreSQL 容器運行中"
else
    print_error "PostgreSQL 容器未運行"
fi

if [ "$REDIS_STATUS" = "1" ]; then
    print_success "Redis 容器運行中"
else
    print_error "Redis 容器未運行"
fi

# 測試總結
print_header "測試總結"

print_success "基本功能測試完成"
echo ""
print_info "下一步:"
echo "  1. 上傳 PPTX: curl -X POST '$BASE_URL/api/decks/' -F 'file=@your.pptx'"
echo "  2. 查看完整測試指南: cat MANUAL_TEST_GUIDE.md"
echo "  3. 運行 Python 測試: python3 test_milestone5_simple.py"
echo ""
print_info "查看日誌:"
echo "  docker logs insightguide-backend --tail 50"
echo ""
