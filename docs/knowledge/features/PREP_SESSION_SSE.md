# Prep Session 實時事件推送 (SSE)

## 概述

後端提供 Prep Session 的 Server-Sent Events (SSE) 端點，可傳遞狀態事件。文件分析的逐步進度目前走 Document event channel；現行管理後台尚未訂閱 Prep Session SSE，而是以 REST 載入與手動刷新資料。

## 功能

### 後端

#### SSE 端點

```
GET /api/prep-sessions/{prep_session_id}/events
```

返回 Server-Sent Events 流，推送 prep session 相關的實時事件。

**事件類型：**

1. **PREP_STATUS_CHANGED** - Prep session 狀態變更
   ```json
   {
     "type": "PREP_STATUS_CHANGED",
     "prepSessionId": "doc_64c30ba7a2c5",
     "status": "ready",
     "documentId": "doc_64c30ba7a2c5",
     "timestamp": "2026-05-26T12:00:00.000Z"
   }
   ```

2. **ANALYSIS_PROGRESS** - 文件分析進度目前發布至 Document channel
   ```json
   {
     "type": "ANALYSIS_PROGRESS",
     "message": "正在為訪談單元產生提問重點...",
     "phase": "cards",
     "current_theme": 2,
     "total_themes": 5,
     "percentage": 40,
     "timestamp": "2026-05-26T12:00:00.000Z"
   }
   ```

   訂閱端點為：

   ```text
   GET /api/documents/{document_id}/events
   ```

#### 事件發布

在 `document_analysis_worker.py` 中：

- 文件分析過程會向 Document channel 發布 `ANALYSIS_PROGRESS`、`THEME_CARDS_CREATED` 與 `ANALYSIS_COMPLETE`。
- 分析完成後會把相關 Prep Session 狀態更新為 `ready`。
- `PREP_STATUS_CHANGED` 事件由 Prep Session 路由的狀態修正流程發布；一般分析完成通知仍以 Document channel 的 `ANALYSIS_COMPLETE` 為準。

### 前端

#### 目前前端行為

目前沒有 `usePrepSessionEvents` Hook。

`PrepSessionListPage.tsx` 是系統管理頁面，會：

- 進入頁面時以 REST 載入專案、受訪者與 Session。
- 使用者按下「刷新」時重新載入資料。
- 不會自動為 preparing 狀態建立 EventSource。

若未來需要即時更新，應新增專用 Hook，並選擇訂閱全域 Prep Session channel 或各 Document channel，避免同一頁同時建立重複 Redis/SSE 訂閱。

## 架構

```
┌─────────────────────┐
│  document_analysis_ │
│      worker         │
│                     │
│  1. 分析完成         │
│  2. 更新 DB status  │
│  3. 發布 Document   │
│     SSE 事件        │
└──────────┬──────────┘
           │
           │ publish to Redis
           ↓
┌─────────────────────┐
│   Event Service     │
│   (Redis Pub/Sub)   │
└──────────┬──────────┘
           │
           │ broadcast
           ↓
┌─────────────────────┐       ┌─────────────────────┐
│  SSE Endpoint       │◄──────│  Frontend Client    │
│  /documents/        │       │  (EventSource)      │
│  {id}/events        │       │  editor/progress UI │
└─────────────────────┘       └─────────────────────┘
```

## 測試

### 手動測試

1. 上傳一個新的文件（會創建 `preparing` 狀態的 prep session）
2. 訂閱 `/api/documents/{document_id}/events`
3. 觀察 `ANALYSIS_PROGRESS` 與 `ANALYSIS_COMPLETE`
4. 回到系統管理後台按下「刷新」，確認 Prep Session 狀態已變成 `ready`

目前沒有獨立的 Prep Session SSE integration test script；自動化時應直接針對上述兩個 SSE 端點建立 API integration test。

### 使用 curl 測試

```bash
curl -N -H "Accept: text/event-stream" \
  "http://localhost:8002/api/prep-sessions/{prep_session_id}/events"
```

## 相關文件

- Backend: `app/api/routes/prep_sessions.py`
- Worker: `app/workers/document_analysis_worker.py`
- Event Service: `app/services/event_service.py`
- Frontend Page: `frontend/src/routes/PrepSessionListPage.tsx`
