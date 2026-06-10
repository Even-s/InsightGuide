#!/bin/bash
# InsightGuide 診斷腳本

echo "========================================="
echo "InsightGuide 診斷報告"
echo "========================================="
echo ""

# 1. 檢查服務狀態
echo "1. 服務狀態檢查"
echo "---"
echo -n "後端 (8001): "
if curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo "✅ 運行中"
else
    echo "❌ 未運行"
fi

echo -n "前端 (5173): "
if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo "✅ 運行中"
else
    echo "❌ 未運行"
fi

echo -n "PostgreSQL (5432): "
if nc -z localhost 5432 2>/dev/null; then
    echo "✅ 運行中"
else
    echo "❌ 未運行"
fi

echo -n "Redis (6379): "
if nc -z localhost 6379 2>/dev/null; then
    echo "✅ 運行中"
else
    echo "❌ 未運行"
fi

echo ""

# 2. 檢查特定 deck
echo "2. Deck 檢查 (deck_1090369d8f0b)"
echo "---"
DECK_ID="deck_1090369d8f0b"
DECK_RESPONSE=$(curl -s "http://localhost:8001/api/decks/$DECK_ID")
DECK_TITLE=$(echo "$DECK_RESPONSE" | jq -r '.title // "未找到"')
DECK_STATUS=$(echo "$DECK_RESPONSE" | jq -r '.status // "未找到"')
echo "標題: $DECK_TITLE"
echo "狀態: $DECK_STATUS"
echo ""

# 3. 檢查 Prep Sessions
echo "3. Prep Sessions 檢查"
echo "---"
PREP_COUNT=$(curl -s "http://localhost:8001/api/prep-sessions/?deckId=$DECK_ID" | jq -r '.prepSessions | length // 0')
echo "現有 prep sessions 數量: $PREP_COUNT"

if [ "$PREP_COUNT" -eq 0 ]; then
    echo "⚠️  沒有 prep session，嘗試創建..."
    CREATE_RESULT=$(curl -s -X POST "http://localhost:8001/api/prep-sessions/" \
      -H "Content-Type: application/json" \
      -d "{\"deckId\":\"$DECK_ID\",\"title\":\"Auto Created Session\"}")

    NEW_PREP_ID=$(echo "$CREATE_RESULT" | jq -r '.id // "創建失敗"')
    echo "創建結果: $NEW_PREP_ID"

    if [ "$NEW_PREP_ID" != "創建失敗" ] && [ "$NEW_PREP_ID" != "null" ]; then
        echo "✅ 成功創建 prep session: $NEW_PREP_ID"
        echo "更新狀態為 ready..."
        curl -s -X PATCH "http://localhost:8001/api/prep-sessions/$NEW_PREP_ID" \
          -H "Content-Type: application/json" \
          -d '{"status":"ready"}' > /dev/null
        echo "✅ 狀態已更新"
    fi
fi

echo ""

# 4. 測試頁面訪問
echo "4. 測試訪問"
echo "---"
echo "請訪問: http://localhost:5173/presenter/$DECK_ID"
echo ""
echo "如果還是進不去，請:"
echo "1. 打開瀏覽器開發者工具 (F12)"
echo "2. 查看 Console 頁籤的錯誤訊息"
echo "3. 查看 Network 頁籤，看哪個 API 請求失敗了"
echo ""

# 5. 後端日誌
echo "5. 最近的後端日誌"
echo "---"
if [ -f /tmp/insightguide-backend.log ]; then
    tail -10 /tmp/insightguide-backend.log
else
    echo "⚠️  找不到日誌文件"
fi

echo ""
echo "========================================="
echo "診斷完成"
echo "========================================="
