#!/bin/bash

# 測試演講模式卡片高亮功能
# 此腳本協助驗證前後端整合

echo "=========================================="
echo "測試演講模式卡片高亮功能"
echo "=========================================="
echo ""

# 檢查後端是否運行
echo "1. 檢查後端服務..."
curl -s http://localhost:8001/health > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✓ 後端服務運行中"
else
    echo "   ✗ 後端服務未運行，請先啟動 backend"
    exit 1
fi

# 檢查前端是否運行
echo "2. 檢查前端服務..."
curl -s http://localhost:5173 > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✓ 前端服務運行中"
else
    echo "   ✗ 前端服務未運行，請先啟動 frontend"
    exit 1
fi

echo ""
echo "=========================================="
echo "手動測試步驟："
echo "=========================================="
echo ""
echo "1. 瀏覽器打開 http://localhost:5173"
echo "2. 上傳一個簡報檔案（或使用現有的 Deck）"
echo "3. 進入編輯模式，確保有主題卡片"
echo "4. 點擊「開始演講」進入演講模式"
echo "5. 點擊「開始錄音」按鈕"
echo "6. 開始講述第一張卡片的主題"
echo ""
echo "=========================================="
echo "預期結果："
echo "=========================================="
echo ""
echo "演講開始前："
echo "  ✓ 所有卡片都顯示「完成度 0%」和灰色空進度條"
echo "  ✓ 一眼看出有多少卡片需要講"
echo ""
echo "當你講到某個主題時："
echo "  ✓ 該卡片自動放大並高亮（藍紫漸變光圈）"
echo "  ✓ 卡片頂部顯示大號百分比（例如 25%）"
echo "  ✓ 顯示演講重點區塊（藍色背景）"
echo "  ✓ 卡片自動滾動到可見區域"
echo "  ✓ 進度條變粗且使用漸變色，動態更新"
echo "  ✓ 其他卡片仍顯示各自的進度（0% 或其他值）"
echo ""
echo "當你講完該主題時："
echo "  ✓ 百分比達到 100%"
echo "  ✓ 卡片變為綠色（covered）"
echo "  ✓ 卡片縮小並半透明"
echo "  ✓ 顯示已講內容摘要"
echo "  ✓ 進度條變為綠色滿進度條"
echo ""
echo "=========================================="
echo "除錯提示："
echo "=========================================="
echo ""
echo "如果卡片沒有高亮："
echo "  • 打開瀏覽器開發者工具（F12）"
echo "  • 查看 Console 標籤"
echo "  • 確認是否有 'Card listening:' 日誌"
echo "  • 檢查 Network 標籤中的 SSE 連接"
echo ""
echo "如果百分比不更新："
echo "  • 檢查後端日誌：cd backend && docker-compose logs -f"
echo "  • 查看是否有 'Card X updated' 日誌"
echo "  • 確認 topic_matching_engine 正常運作"
echo ""
echo "=========================================="
