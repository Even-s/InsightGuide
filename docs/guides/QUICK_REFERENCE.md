# 🚀 SlideCue 快速參考卡

**最後更新**: 2026-05-25

---

## 📊 系統狀態速覽

| 項目 | 狀態 | 詳情 |
|------|------|------|
| **整體完成度** | 85% | ✅ MVP 接近完成 |
| **基礎設施** | ✅ 100% | 所有服務健康 |
| **後端 API** | ✅ 95% | 功能完整 |
| **前端 UI** | 🟡 80% | 需測試 |
| **文檔** | ✅ 98% | 423 個文件 |

---

## 🌐 服務 URLs

```
前端:    http://localhost:5173
後端:    http://localhost:8001
API文檔: http://localhost:8001/docs
MinIO:   http://localhost:9001 (minioadmin/minioadmin)
```

---

## 🔧 常用命令

### 啟動服務
```bash
# 啟動基礎設施
docker-compose up -d

# 啟動後端
cd backend && source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# 啟動前端
cd frontend && npm run dev
```

### 健康檢查
```bash
# 檢查 Docker
docker-compose ps

# 檢查後端
curl http://localhost:8001/health

# 檢查資料庫
docker exec slidecue-postgres pg_isready -U slidecue
```

### 清理資料庫
```bash
# 結束所有舊 sessions
docker exec slidecue-postgres psql -U slidecue -d slidecue \
  -c "UPDATE presentation_sessions SET status='ended', ended_at=NOW() WHERE status IN ('paused','presenting');"
```

---

## 📦 技術棧版本

### 前端
- React: 18.3.1
- TypeScript: 5.9.3
- Vite: 5.4.21
- Tailwind: 3.4.19
- Zustand: 4.5.7

### 後端
- Python: 3.11.15
- FastAPI: 0.109.2
- SQLAlchemy: 2.0.27
- OpenAI: 1.51.0
- Celery: 5.3.6

### 基礎設施
- PostgreSQL: 16 + pgvector
- Redis: 7
- MinIO: latest

---

## 📝 Milestone 狀態

```
✅ M1: Upload (100%)     - PPTX 上傳與轉換
✅ M2: Analysis (100%)   - AI 分析與卡片生成
🟡 M3: Editor (75%)      - 編輯器模式
✅ M4: Whisper (100%)    - 語音轉錄
✅ M5: Matching (100%)   - 主題匹配引擎
🟡 M6: Presenter (90%)   - 演講者介面
❌ M7: Report (0%)       - 會話報告
```

---

## 🔍 問題排查

### Timer 顯示異常時間？
```bash
# 結束舊 session
docker exec slidecue-postgres psql -U slidecue -d slidecue \
  -c "UPDATE presentation_sessions SET status='ended', ended_at=NOW() WHERE status='paused';"

# 或在 UI 點擊「結束」按鈕重新開始
```

### Whisper 產生幻覺文字？
- 已修復：Temperature=0 + 過濾器
- 確認使用最新版本

### 轉錄速度慢？
- 已優化：3秒 chunk + 語音檢測
- 查看 `../archive/TRANSCRIPTION_SPEED_IMPROVEMENTS.md`

---

## 📚 關鍵文檔

### 必讀
- `README.md` - 專案說明
- `QUICKSTART.md` - 快速開始
- `SlideCue_開發架構書.md` - 主架構

### 健康檢查
- `SYSTEM_HEALTH_CHECK_REPORT.md` - 完整報告
- `HEALTH_CHECK_SUMMARY.md` - 執行摘要

### Milestone
- `MILESTONE_2_SUMMARY.md` - AI 分析
- `MILESTONE_4_SUMMARY.md` - Realtime 轉錄
- `MILESTONE_5_COMPLETE.md` - 主題匹配
- `MILESTONE_6_SUMMARY.md` - 前端 UI

### 問題修復
- `TIMER_480_FINAL_FIX.md` - 計時器修復
- `../fixes/REALTIME_MATCHING_AND_HALLUCINATION_FILTER.md` - 幻覺過濾與語意匹配

---

## 🎯 立即行動

### 今天
1. 清理 paused sessions
2. 測試完整演講流程

### 本週
3. 實作 Milestone 7
4. 完整端到端測試

### 未來
5. 性能優化
6. 生產部署準備

---

## 📞 支援

**專案位置**: `/Users/cfh00914977/Project/SlideCue`

**檔案統計**:
- Python: 3,908 檔案
- TypeScript: 37 檔案  
- Markdown: 423 檔案
- 總大小: 409 MB

---

✅ **系統健康，可以繼續開發！**

*更新於: 2026-05-25 14:50*
