# InsightGuide 快速啟動指南

---

## 前置需求

- Node.js 18+
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

## 一鍵啟動（推薦）

```bash
cd InsightGuide

# 啟動所有服務
./insightguide.sh launch
```

腳本會自動啟動 Docker services、安裝依賴、執行 migrations、啟動後端 + Celery + 前端。

---

## 手動啟動

### 1. 環境配置

```bash
cp backend/.env.example backend/.env
# 編輯 backend/.env，填入 OPENAI_API_KEY
```

### 2. Docker Services

```bash
docker-compose -f docker-compose.full.yml up -d postgres redis minio
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

1. 上傳 BRD 文件（PDF / DOCX / Markdown）
2. 等待 AI 分析產生訪談主題與問題卡
3. 在編輯模式調整問題順序與重要性
4. 進入訪談模式，開啟麥克風即時轉錄
5. 訪談結束後查看報告與 BRD 草稿

---

## 常見問題

**Docker 無法啟動**：確認 Docker Desktop 正在運行，執行 `docker ps` 驗證。

**資料庫連接失敗**：`docker-compose -f docker-compose.full.yml logs postgres` 查看日誌。

**OpenAI API 錯誤**：確認 `backend/.env` 中 `OPENAI_API_KEY` 已正確設定。

**前端無法連接後端**：確認 `frontend/.env` 中 `VITE_API_URL=http://localhost:8002`。
