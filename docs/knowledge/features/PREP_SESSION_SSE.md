# Prep Session 實時事件推送 (SSE)

## 概述

使用 Server-Sent Events (SSE) 實現 prep session 狀態的實時更新，讓用戶可以即時看到文件分析進度和狀態變更。

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
     "deckId": "doc_64c30ba7a2c5",
     "timestamp": "2026-05-26T12:00:00.000Z"
   }
   ```

2. **ANALYSIS_PROGRESS** - 文件分析進度（未來功能）
   ```json
   {
     "type": "ANALYSIS_PROGRESS",
     "prepSessionId": "doc_64c30ba7a2c5",
     "currentSlide": 5,
     "totalSlides": 21,
     "percentage": 23.8,
     "timestamp": "2026-05-26T12:00:00.000Z"
   }
   ```

#### 事件發布

在 `document_analysis_worker.py` 中，當文件分析完成時：
- 更新 prep session 狀態從 `preparing` -> `ready`
- 發布 `PREP_STATUS_CHANGED` 事件到所有訂閱的客戶端

### 前端

#### Hook: `usePrepSessionEvents`

位置：`frontend/src/hooks/usePrepSessionEvents.ts`

**使用方式：**

```tsx
import { usePrepSessionEvents } from '@/hooks/usePrepSessionEvents';

function MyComponent({ prepSessionId }) {
  usePrepSessionEvents(prepSessionId, {
    onPrepStatusChanged: (event) => {
      console.log('Status changed:', event.status);
    },
    onAnalysisProgress: (event) => {
      console.log('Progress:', event.percentage);
    },
    onError: (error) => {
      console.error('SSE error:', error);
    }
  });

  return <div>...</div>;
}
```

#### PrepSessionListPage 整合

在 `PrepSessionListPage.tsx` 中：
- 自動為所有 `preparing` 狀態的 prep sessions 建立 SSE 連接
- 當收到 `PREP_STATUS_CHANGED` 事件時，更新列表中的狀態
- 重新載入統計數據

## 架構

```
┌─────────────────────┐
│  document_analysis_ │
│      worker         │
│                     │
│  1. 分析完成         │
│  2. 更新 DB status  │
│  3. 發布 SSE 事件   │
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
│  /prep-sessions/    │       │  (EventSource)      │
│  {id}/events        │       │                     │
└─────────────────────┘       └─────────────────────┘
```

## 測試

### 手動測試

1. 上傳一個新的文件（會創建 `preparing` 狀態的 prep session）
2. 打開 Prep Sessions 頁面
3. 觀察列表中的狀態
4. 當分析完成時，狀態會自動從 `preparing` 變成 `ready`

### 使用測試腳本

```bash
cd /Users/cfh00914977/Project/InsightGuide
python scripts/integration_tests/test_prep_session_sse.py
```

### 使用 curl 測試

```bash
curl -N -H "Accept: text/event-stream" \
  "http://localhost:8002/api/prep-sessions/{prep_session_id}/events"
```

## 相關文件

- Backend: `app/api/routes/prep_sessions.py`
- Worker: `app/workers/document_analysis_worker.py`
- Event Service: `app/services/event_service.py`
- Frontend Hook: `frontend/src/hooks/usePrepSessionEvents.ts`
- Frontend Page: `frontend/src/routes/PrepSessionListPage.tsx`
