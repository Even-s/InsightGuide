# InsightGuide - AI 需求訪談輔助系統

InsightGuide 是一款 AI 驅動的需求訪談輔助系統，透過 OpenAI Realtime API 即時追蹤訪談重點，協助需求分析師更完整、系統化地完成需求訪談。

---

## 專案狀態

**版本**: v0.2.0
**開發階段**: 核心功能完成，進入優化階段
**最後更新**: 2026-07-23

### 實施統計
- **後端服務**: 27 個 service files
- **資料模型**: 24 個 models
- **API Routes**: 17 個 route files
- **前端頁面**: 12 個 pages
- **React Hooks**: 11 個 custom hooks

---

## 啟動

```bash
./insightguide.sh launch
```

常用指令：

| 指令 | 說明 |
|------|------|
| `./insightguide.sh` | 互動式控制中心 |
| `./insightguide.sh start` | 啟動所有服務（已運行的服務不會重啟） |
| `./insightguide.sh launch` | 啟動所有服務並開啟瀏覽器 |
| `./insightguide.sh restart` | 完整重啟所有服務 |
| `./insightguide.sh restart backend` | 只重啟後端（也可指定 `celery` / `frontend`） |
| `./insightguide.sh status` | 檢查服務狀態與健康度 |
| `./insightguide.sh logs` | 查看近期 log |
| `./insightguide.sh tail` | 持續追蹤 log |
| `./insightguide.sh stop` | 停止所有服務 |

macOS 使用者也可以雙擊 `InsightGuide.command` 啟動，或雙擊 `StopInsightGuide.command` 關閉所有服務。
啟動器會在需要時開啟 Docker Desktop，並等待 PostgreSQL、Redis、MinIO、後端、Celery 與前端就緒。

在新的 Mac 上，可雙擊 `InstallInsightGuide.command` 安裝 Homebrew、Node.js、Python 3.11、Docker Desktop 與全部專案依賴。

**服務端口**：
- 前端：http://localhost:5174
- 後端 API：http://localhost:8002
- API 文件：http://localhost:8002/docs
- MinIO Console：http://localhost:9001

---

## 功能

### 快速 Demo 訪談
- 首頁可直接選擇「現況流程探索」、「痛點與需求探索」或「新系統需求確認」公版模板
- 後端在單一交易中建立獨立暫存 Project、預設受訪角色、完整訪談指南與 Interview Session，不經 Celery 或文件分析
- 建立後直接沿用正式 PresenterPage；Demo 專案不會出現在正式專案列表，24 小時到期後會在後續建立 Demo 時清理

### 需求文件上傳與分析
- 上傳 API 接受 PDF、Word、Markdown 與純文字；目前分析 worker 僅可靠解析 UTF-8 Markdown／純文字，PDF／Word 二進位內容擷取尚未實作
- AI 自動分析文件內容，產生訪談主題與問題卡片（Question Cards）
- 每張卡片包含 coverage rules、semantic anchors、expected keywords

### 編輯模式
- 檢視文件章節與 Question Cards
- 拖放排序、內聯編輯、問題簡化、追問清理與重新生成
- 設定卡片重要性（must / should / optional）

### 訪談模式
- 透過 OpenAI Realtime API (WebRTC) 即時語音轉錄
- 動態 Question Card 追蹤與狀態顯示
- 即時充分度統計與進度追蹤
- 支援手動覆蓋卡片狀態與鍵盤導覽

### 訪談後分析
- **Insight Memo**：自動萃取痛點、需求線索、限制假設、未解問題
- **完整逐字稿**：直接保留 Realtime 完成辨識的逐字稿，不另行錄音或區分說話者
- **訪談紀錄**：以每輪累積洞察與各場 Realtime 逐字稿作為正式紀錄

### 專案級管理（多訪談整合）
- **Stakeholder Plan**：AI 建議角色槽位，追蹤訪談進度
- **Role-based Card Filtering**：根據受訪者角色篩選適合的問題
- **Interview Brief**：根據角色 + evidence gap 產生訪談前指引
- **Interview Series / Round**：同一受訪者與主題可建立多輪獨立大綱，每輪可由多次 Session 續訪完成
- **Round Aggregate**：每輪只對外提供一份最新版累積洞察、覆蓋與證據快照
- **Evidence Matrix**：跨訪談需求整合與去重
- **BRD Readiness**：評估證據充足度，守門 BRD 生成

### BRD 文件生成
- 專案模式：從 Round Aggregate / Evidence Matrix 整合多訪談證據產生完整 BRD
- BRD Readiness 會先檢查證據是否足夠，再進入生成流程
- 目前產出並快取 Markdown；PDF 匯出尚未實作

---

## 架構

| 層級 | 技術 |
|------|------|
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS + React Router；以 React hooks／元件狀態管理 |
| 後端 | Python 3.11 + FastAPI + SQLAlchemy + Pydantic |
| 背景任務 | Celery + Redis；目前只註冊文件分析 worker |
| 資料庫 | PostgreSQL + pgvector |
| 物件儲存 | MinIO (S3-compatible) |
| AI | GPT-4o（初始 themes/cards）、GPT-5.5（卡片 metadata）、GPT-5.4-mini（語意與專案分析）、Realtime API |

本機採 hybrid topology：PostgreSQL、Redis、MinIO 在 Docker，FastAPI、Celery、Vite 在主機執行。EC2 prototype 則以單機 Docker Compose 運行完整服務，並由 Caddy 提供 TLS、React SPA、API／SSE 反向代理與檔案網域。

本機啟動會先執行 `alembic upgrade head`；EC2 deploy／restore 另採 clean-v2 fail-closed gate，拒絕無 Alembic 版本的非空 schema，並檢查 retired table／column。認證目前仍是單一使用者開發 stub，不可視為正式的多使用者權限邊界。

完整架構文件請參考 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

---

## 前置需求

- Node.js 20+
- Python 3.11+
- Docker & Docker Compose
- OpenAI API Key

詳細設定請參考 [`docs/QUICKSTART.md`](docs/QUICKSTART.md)。

---

## 文件

| 文件 | 說明 |
|------|------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 系統架構與技術規格 |
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | 快速啟動指南 |
| [docs/FUNCTIONAL_TEST_PLAN.md](docs/FUNCTIONAL_TEST_PLAN.md) | 全系統功能測試案例、優先級與自動化里程碑 |
| [docs/REFACTORING_PLAN.md](docs/REFACTORING_PLAN.md) | 歷史：已完成的多訪談架構重構計劃 |
| [docs/improvement_plan_v2.md](docs/improvement_plan_v2.md) | 歷史：已完成的逐字稿與卡片匹配改進計劃 |
| [docs/knowledge/](docs/knowledge/) | AI 模型設定與功能知識文件 |

---

## 授權

Copyright © 2026 InsightGuide Team. 保留所有權利。
