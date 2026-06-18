# InsightGuide - AI 需求訪談輔助系統

InsightGuide 是一款 AI 驅動的需求訪談輔助系統,透過 OpenAI Realtime API 即時追蹤訪談重點，協助需求分析師更完整、系統化地完成需求訪談。

---

## Project Status

**Overall Progress**: **90% Core Complete**  
**Current Focus**: Frontend polish & production hardening  
**Version**: v0.2.0

**Documentation**:
- [Architecture](docs/ARCHITECTURE.md) - System architecture & technical spec
- [Refactoring Plan](docs/REFACTORING_PLAN.md) - Historical: completed transformation plan
- [Quick Start](docs/QUICKSTART.md) - Setup guide

---

## 專案描述

InsightGuide 是一款智慧需求訪談輔助系統，協助需求分析師即時掌握訪談進度。

系統使用 OpenAI Realtime API 即時轉錄訪談內容，自動產生訪談問題卡片，並追蹤每個問題的回答充分度。透過結合 GPT-5.5 需求文件分析與問題生成、GPT-5.4-mini 語意判斷、embedding 相似度、關鍵字與事實匹配，InsightGuide 可以判斷問題回答是否足夠撰寫 BRD 文件，並在訪談模式中即時顯示完成百分比與建議追問重點。

## 像 App 一樣啟動

本機開發時可以把 InsightGuide 當成一個由 Codex 或 macOS 雙擊啟動的網頁 app：

```bash
./insightguide.sh launch
```

常用入口：

- `./insightguide.sh`：開啟互動式控制中心。
- `./insightguide.sh launch`：需要時啟動服務，完成後開啟 `http://localhost:5174`。
- `./insightguide.sh restart`：完整重啟 Docker、後端、Celery 與前端。
- `./insightguide.sh status`：檢查服務狀態與健康度。
- `./insightguide.sh logs` / `./insightguide.sh tail`：查看近期 log 或持續追蹤 log。
- `./insightguide.sh stop`：停止所有服務。

在 macOS Finder 中也可以雙擊 `InsightGuide.command`，它會啟動服務並開啟 InsightGuide 網頁。

## 功能

### 準備模式

- 上傳需求草稿文件（支援 PDF、Word、Markdown）後自動建立 PrepSession，將「訪談準備」與「實際訪談紀錄」分離。
- 自動分析文件內容，並以 AI 產生訪談問題卡片（Question Cards）。
- 使用 `preparing` / `ready` 狀態管理分析進度，分析完成後即可重複建立多次 InterviewSession 練習。
- 支援 PrepSession 清單、狀態顯示、展開查看歷次訪談紀錄，以及單筆或全部刪除。
- 刪除 PrepSession 時會在同一個資料庫交易中清除 document、sections、question cards、interview sessions、card states 與 utterances，避免殘留資料。

### 編輯模式

- 檢視需求文件章節與 Question Cards，調整卡片順序、重要性與問題內容。
- Question Cards 最多顯示三個父層重點，並可透過隱藏 subpoints 要求更細的回答條件。
- 支援卡片拖放排序、內聯編輯、問題簡化、追問清理與重新生成。
- AI 產生的 coverage rules 會和後續訪談模式的充分度判斷對齊。

### 訪談模式

- 透過 OpenAI Realtime transcription + WebRTC 取得低延遲即時逐字稿。
- 逐字稿串流期間先做 partial transcript matching，讓 Question Cards 可在受訪者還沒停頓前更新回答水位。
- 完整 utterance 儲存後觸發 Script Plan advance，更新 Smart Prompt 建議追問游標。
- Question Card 充分度與 Smart Prompt 進度彼此獨立：卡片 SSE 只更新卡片狀態，Script Plan 只由完整逐字稿或手動 `下一個問題` 推進。
- Interviewer UI 顯示即時完成百分比、卡片狀態、回答水位、兩行式建議追問與明確的 `建議問題已完成` 狀態。
- 支援手動切換下一個問題、手動覆蓋卡片狀態、鍵盤導覽與訪談結束後報告入口。

### 智慧追問與進度判斷

- Script Plan 會依據目前章節與尚未完成的 Question Cards 產生後續建議追問句。
- GPT 語意判斷會比較「預期回答要點」與「實際訪談逐字稿」，支援 `advance`、`hold`、`skip_to_matched`、`regenerate`、`ignore` 等動作。
- Whisper 幻覺過濾會攔截靜音或雜訊中常見的短句，例如無意義笑聲、訂閱提示或重複短語，避免誤推進進度。
- Script Plan regeneration 會排除已充分回答的卡片，讓重新規劃聚焦在尚未問到的內容。

### 訪談報告

- 訪談結束後產生整體覆蓋率、must / should question 覆蓋率、逐 question 分析、時間軸、語速、字數與每個章節停留時間。
- 前端提供圖表、重點摘要、改善建議與 responsive report view。
- 支援 JSON 與 PDF 匯出，檔案上傳至 MinIO / S3-compatible storage 並提供 presigned download URL。
- **BRD 文件草稿生成**：根據訪談內容自動生成 BRD 文件初稿，包含需求描述、功能清單、使用者故事等。

## 開發歷史與技術取捨 log

以下整理自 `docs/` 內的 milestone、health check、debug 與 archive 文件。重點不只列出目前完成項目，也記錄開發過程中試過、修正、暫停或淘汰的技術方案，方便後續判斷不要再走回已驗證不適合的路。

### 1. 需求文件上傳 / 文件處理

**目標**: 讓使用者上傳需求草稿文件後，系統可以自動分析、擷取章節、建立後續分析所需資料。

- 已完成 PDF / Word / Markdown 上傳、轉檔、章節擷取與背景分析流程。
- 後端以 FastAPI 提供 API，Celery + Redis 處理文件分析與長任務。
- 使用 PostgreSQL 保存 document、sections、question cards、interview sessions 等資料，MinIO / S3-compatible storage 保存檔案與匯出報告。

### 2. PrepSession 準備模式

**目標**: 把「一份文件的準備資料」和「每一次實際訪談紀錄」分開。

- 建立 `PrepSession -> InterviewSession` 兩層架構。
- 一份 document 對應一個準備單位，同一個準備單位可重複練習多次。
- `preparing` 表示 AI 分析中，`ready` 表示可進入編輯與訪談。

### 3. AI 需求文件分析 / Question Cards

**目標**: 從需求文件內容產生訪談者真正需要追蹤的問題卡片。

- 使用 GPT-5.5 做文件分析與 Question Card 生成。
- 每張 Question Card 包含重要性、建議追問、coverage rules、semantic anchors、expected keywords、must mention facts。

## 目前狀態

**最後更新**: 2026-06-17  
**開發階段**: 核心功能完成，進入優化階段  
**版本**: v0.2.0

### 完成的功能模組
- Document analysis & question card generation
- Real-time interview with WebRTC transcription
- Answer evaluation engine (embedding + AI judge)
- Project & stakeholder management
- Insight memo generation (post-interview analysis)
- Evidence matrix (cross-interview requirement consolidation)
- BRD readiness assessment & generation
- Role-based card filtering & interview briefs
- Prompt registry with version management

### 實施統計
- **後端服務**: 38 個 service files
- **資料模型**: 27 個 models
- **API Routes**: 16 個 route files
- **前端頁面**: 14 個 pages
- **React Hooks**: 7 個 custom hooks

## 架構

InsightGuide 採用模組化架構，明確分離各層責任：

- **前端**: React + TypeScript + Vite + Tailwind CSS + Zustand
- **後端**: Python + FastAPI
- **背景任務**: Celery + Redis，用於背景任務處理
- **資料庫**: PostgreSQL，搭配 pgvector extension
- **快取與佇列**: Redis
- **物件儲存**: S3-compatible storage，本機開發使用 MinIO
- **AI 服務**: OpenAI Responses API、Realtime Transcription API、GPT-5.5 文件/問題生成、GPT-5.4-mini 語意判斷、Embeddings

完整架構文件請參考 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

## 前置需求

- **Node.js** 18+ 與 npm
- **Python** 3.11+
- **Docker** 與 Docker Compose
- **LibreOffice**，用於文件轉換
- **Poppler**，用於 PDF 處理
- **OpenAI API key**，所有 AI 功能皆需要
- **PostgreSQL**，需支援 pgvector extension，可透過 Docker 啟動
- **Redis**，可透過 Docker 啟動

### 前端關鍵套件

| 套件 | 用途 |
|------|------|
| `react-markdown` | 核心 Markdown 渲染引擎 |
| `remark-gfm` | GFM 擴充：表格、刪除線、任務清單、自動連結 |
| `rehype-slug` | 標題自動加 id，支援頁內錨點跳轉 |
| `rehype-autolink-headings` | 標題加上可點擊的錨點連結 |
| `@tailwindcss/typography` | 為 Markdown 內容提供 `prose` 排版樣式（標題、段落、表格、引用等） |

安裝方式（已包含在 `package.json`，一般 `npm install` 即會安裝）：

```bash
cd frontend
npm install react-markdown remark-gfm rehype-slug rehype-autolink-headings @tailwindcss/typography
```

`@tailwindcss/typography` 需在 `tailwind.config.js` 的 `plugins` 中啟用：

```js
plugins: [
  require('@tailwindcss/typography'),
]
```

## 快速開始

### ⚡ 一鍵啟動（推薦）

```bash
# 使用單一指令啟動所有服務
./start-services.sh

# 檢查服務狀態
./status.sh

# 停止所有服務
./stop-services.sh
```

**就這樣！** 腳本會自動：
1. 啟動 Docker services（PostgreSQL、Redis、MinIO）
2. 執行資料庫 migrations
3. 啟動後端 API（port 8002）
4. 啟動 Celery worker（背景任務）
5. 啟動前端 dev server（port 5174）

**存取應用程式：**
- **前端**: http://localhost:5174
- **後端 API**: http://localhost:8002
- **API 文件**: http://localhost:8002/docs
- **MinIO Console**: http://localhost:9001 (minioadmin / minioadmin)

## 主要功能

### 📤 需求文件上傳與分析
- 支援拖放上傳需求文件（PDF、Word、Markdown）
- 自動文件分析與章節擷取
- 使用已設定的 document analysis model 進行 AI 分析
- 自動產生具有 coverage rules 的 question cards

### ✏️ 編輯模式
- 視覺化文件章節預覽與導覽
- 拖放整理 question cards
- 編輯建議追問與重點
- 設定卡片重要性（must / should / optional）
- 批次卡片管理與篩選

### 🎯 PrepSession 管理
- **兩層架構**: PrepSession → InterviewSession
- 一個準備單位可包含多筆訪談紀錄
- 自動狀態追蹤：`preparing` 🟡 → `ready` 🟢
- 追蹤訪談進度並比較表現

### 🎤 訪談模式
- 透過 OpenAI Realtime API (WebRTC) 進行即時語音轉錄
- 動態 question card 追蹤與顏色狀態顯示
- 即時充分度統計與進度追蹤
- 對 answered / skipped questions 提供視覺回饋
- 支援鍵盤快捷鍵切換問題
- 支援手動覆蓋卡片狀態

### 📊 訪談報告
- 訪談後充分度分析
- 每個 question 的 evidence transcripts
- 表現洞察與改善建議
- 可匯出的 session summary
- **BRD 文件草稿生成**

## 技術棧

| 層級 | 技術 | 選用原因 |
|-------|------------|------|
| **前端** | React + TypeScript + Vite | 型別安全 components，開發體驗快速 |
| **樣式** | Tailwind CSS | 快速 UI 開發與一致設計 |
| **狀態管理** | Zustand | 輕量，適合即時更新 |
| **後端** | Python + FastAPI | 現代 async framework，自動產生 API docs |
| **背景任務** | Celery + Redis | 成熟穩定的背景任務處理 |
| **資料庫** | PostgreSQL + pgvector | 關聯式資料 + vector similarity search |
| **儲存** | S3-compatible (MinIO) | 儲存檔案與 media 的 object storage |
| **AI/ML** | OpenAI APIs | GPT-5.5 用於文件分析，GPT-5.4-mini 用於語意判斷，Realtime API 用於低延遲轉錄 |

## 文件

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - 系統架構與技術規格
- [docs/QUICKSTART.md](docs/QUICKSTART.md) - 快速啟動指南
- [docs/REFACTORING_PLAN.md](docs/REFACTORING_PLAN.md) - 重構計劃書（已完成）
- [docs/improvement_plan_v2.md](docs/improvement_plan_v2.md) - 逐字稿與卡片匹配改進計劃
- [docs/knowledge/](docs/knowledge/) - AI 模型設定與功能知識文件

## 授權

Copyright © 2026 InsightGuide Team. 保留所有權利。
