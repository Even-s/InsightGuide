# InsightGuide 快速啟動指南

---

## 前置需求

- Node.js 20+
- Python 3.11+
- Docker & Docker Compose
- LibreOffice（文件轉換）
- Poppler（PDF 處理）
- OpenAI API Key

macOS 安裝：
```bash
brew install node python@3.11 docker libreoffice poppler
```

---

## 首次安裝

```bash
cd InsightGuide

# 一鍵安裝：檢查環境、安裝依賴、建立資料庫
./insightguide.sh setup

# 編輯 backend/.env，填入你的 OPENAI_API_KEY
```

安裝腳本會自動完成：
1. 檢查前置需求（Docker、Node.js、Python）
2. 建立 `backend/.env` 環境檔
3. 啟動 Docker 基礎服務（PostgreSQL、Redis、MinIO）
4. 建立 Python 虛擬環境並安裝依賴
5. 執行資料庫 migrations
6. 安裝前端 npm 依賴

---

## 啟動系統

```bash
# 啟動所有服務並開啟瀏覽器
./insightguide.sh launch
```

腳本會啟動 Docker services、後端 + Celery + 前端，並在完成後開啟瀏覽器。

### 其他常用指令

```bash
./insightguide.sh            # 互動式控制中心
./insightguide.sh status     # 檢查服務狀態與健康度
./insightguide.sh restart    # 完整重啟所有服務
./insightguide.sh logs       # 查看近期 log
./insightguide.sh tail       # 持續追蹤 log
./insightguide.sh stop       # 停止所有服務
```

macOS 使用者也可以雙擊 `InsightGuide.command` 以 Finder 啟動。

---

## 手動啟動

### 1. 環境配置

```bash
cp backend/.env.example backend/.env
# 編輯 backend/.env，填入 OPENAI_API_KEY
```

### 2. Docker Services

```bash
docker-compose up -d
```

### 3. 後端

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8002
```

### 4. Celery Worker（另開終端）

```bash
cd backend && source venv/bin/activate
celery -A app.workers.celery_app worker --loglevel=info
```

### 5. 前端（另開終端）

```bash
cd frontend
npm install
npm run dev
```

---

## 服務端口

| 服務 | URL |
|------|-----|
| 前端 | http://localhost:5174 |
| 後端 API | http://localhost:8002 |
| API 文件 (Swagger) | http://localhost:8002/docs |
| MinIO Console | http://localhost:9001 (minioadmin/minioadmin) |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

---

## 驗證

```bash
# 後端健康檢查
curl http://localhost:8002/health

# 前端：瀏覽器開啟 http://localhost:5174
```

---

## 使用流程

### 單次訪談模式

1. 上傳 BRD 文件（PDF / DOCX / Markdown）
2. 等待 AI 分析產生訪談主題與問題卡
3. 在編輯模式調整問題順序與重要性
4. 進入訪談模式，開啟麥克風即時轉錄
5. 訪談結束後查看報告與 BRD 草稿

### 專案模式（多訪談整合）

1. 建立專案，定義 BRD 目標與範圍
2. 系統自動產生 Stakeholder Plan（建議角色槽位）
3. 登錄受訪者，安排訪談
4. 進行訪談，自動產生 Insight Memo
5. 查看 Evidence Matrix（跨訪談需求整合）
6. 確認 BRD Readiness 後生成 BRD

---

## 常見問題

**Docker 無法啟動**：確認 Docker Desktop 正在運行，執行 `docker ps` 驗證。

**資料庫連接失敗**：`docker-compose logs postgres` 查看日誌。

**OpenAI API 錯誤**：確認 `backend/.env` 中 `OPENAI_API_KEY` 已正確設定。

**前端無法連接後端**：確認 `frontend/.env` 中 `VITE_API_URL=http://localhost:8002`。

**insightguide.sh 無法執行**：執行 `chmod +x insightguide.sh`。
