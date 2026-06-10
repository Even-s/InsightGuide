# InsightGuide 快速啟動指南

本指南將協助您在 5 分鐘內啟動 InsightGuide 進行本地開發或測試。

---

## 📋 前置需求檢查

在開始之前，請確認已安裝以下工具：

```bash
# 檢查 Node.js (需要 18+)
node --version

# 檢查 Python (需要 3.11+)
python3 --version

# 檢查 Docker
docker --version
docker-compose --version

# 檢查 LibreOffice (用於文件轉換)
libreoffice --version

# 檢查 Poppler (用於 PDF 處理)
pdfinfo -v
```

如果缺少任何工具，請先安裝：

### macOS
```bash
# 使用 Homebrew 安裝
brew install node python@3.11 docker libreoffice poppler
```

### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install nodejs python3.11 docker.io docker-compose libreoffice poppler-utils
```

---

## 🚀 一鍵啟動

### 方法 1: 使用 insightguide.sh（推薦）

```bash
# 進入專案目錄
cd InsightGuide

# 啟動所有服務
./insightguide.sh launch

# 或者使用互動式選單
./insightguide.sh
```

這個腳本會自動：
1. 啟動 Docker services（PostgreSQL、Redis、MinIO）
2. 安裝 Python 和 Node.js 依賴
3. 執行資料庫 migrations
4. 啟動後端 API
5. 啟動 Celery worker
6. 啟動前端開發伺服器
7. 打開瀏覽器到 http://localhost:5173

### 方法 2: 使用 start-services.sh

```bash
# 啟動所有服務
./start-services.sh

# 檢查服務狀態
./status.sh

# 查看日誌
./insightguide.sh logs
```

### 方法 3: macOS Finder 雙擊啟動

在 macOS 上，可以直接雙擊 `InsightGuide.command` 檔案啟動應用程式。

---

## 🔧 手動啟動（進階）

如果需要更細緻的控制，可以分步驟啟動：

### 1. 環境配置

```bash
# 複製環境變數範例檔案
cp backend/.env.example backend/.env

# 編輯 .env 並填入您的 OpenAI API Key
# OPENAI_API_KEY=sk-your-key-here
```

### 2. 啟動 Docker Services

```bash
# 啟動 PostgreSQL、Redis、MinIO
docker-compose -f docker-compose.full.yml up -d postgres redis minio

# 等待服務就緒（約 10-15 秒）
sleep 15
```

### 3. 設定後端

```bash
cd backend

# 建立虛擬環境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安裝依賴
pip install -r requirements.txt

# 執行資料庫 migrations
alembic upgrade head

# 啟動 FastAPI 伺服器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

### 4. 啟動 Celery Worker（另開終端機）

```bash
cd backend
source venv/bin/activate

# 啟動 worker
celery -A app.workers.celery_app worker --loglevel=info
```

### 5. 啟動前端（另開終端機）

```bash
cd frontend

# 安裝依賴
npm install

# 啟動開發伺服器
npm run dev
```

---

## 🌐 存取應用程式

啟動成功後，可以存取以下 URL：

| 服務 | URL | 說明 |
|------|-----|------|
| **前端應用程式** | http://localhost:5173 | InsightGuide 主介面 |
| **後端 API** | http://localhost:8001 | FastAPI 服務 |
| **API 文件** | http://localhost:8001/docs | Swagger UI |
| **MinIO Console** | http://localhost:9001 | 物件儲存管理 (minioadmin/minioadmin) |
| **PostgreSQL** | localhost:5432 | 資料庫 (postgres/postgres) |
| **Redis** | localhost:6379 | 快取與佇列 |

---

## ✅ 驗證安裝

### 1. 檢查後端健康狀態

```bash
curl http://localhost:8001/health
# 預期回應: {"status": "healthy"}
```

### 2. 檢查前端是否載入

在瀏覽器開啟 http://localhost:5173，應該看到 InsightGuide 上傳頁面。

### 3. 檢查 Celery worker

```bash
# 檢查 worker 是否正在運行
./insightguide.sh status

# 或查看 Celery 日誌
./insightguide.sh logs celery
```

### 4. 測試文件上傳

1. 準備一個測試文件（PDF、DOCX 或 Markdown）
2. 在前端上傳文件
3. 檢查是否能看到分析進度
4. 分析完成後應該能看到生成的問題卡片

---

## 🛠️ 常見問題排除

### 問題 1: Docker services 無法啟動

```bash
# 檢查 Docker 是否運行
docker ps

# 如果 Docker 未運行，啟動 Docker Desktop（macOS/Windows）
# 或啟動 Docker 服務（Linux）
sudo systemctl start docker

# 重新啟動 services
docker-compose -f docker-compose.full.yml restart
```

### 問題 2: 資料庫連接失敗

```bash
# 檢查 PostgreSQL 是否就緒
docker-compose -f docker-compose.full.yml ps postgres

# 查看 PostgreSQL 日誌
docker-compose -f docker-compose.full.yml logs postgres

# 重新執行 migrations
cd backend
source venv/bin/activate
alembic upgrade head
```

### 問題 3: OpenAI API 錯誤

```bash
# 確認 API Key 已正確設定
cd backend
cat .env | grep OPENAI_API_KEY

# 測試 API Key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### 問題 4: 前端無法連接後端

```bash
# 檢查後端是否在運行
curl http://localhost:8001/health

# 檢查前端環境變數
cd frontend
cat .env | grep VITE_API_BASE_URL
# 應該是: VITE_API_BASE_URL=http://localhost:8001
```

### 問題 5: Celery worker 未處理任務

```bash
# 檢查 Redis 連接
redis-cli ping
# 預期回應: PONG

# 重啟 Celery worker
./insightguide.sh restart celery

# 查看 worker 日誌
./insightguide.sh tail celery
```

---

## 📚 下一步

安裝成功後，您可以：

1. **上傳第一個需求文件**
   - 點擊上傳按鈕
   - 選擇 PDF、DOCX 或 Markdown 文件
   - 等待 AI 分析完成

2. **檢視生成的問題卡片**
   - 分析完成後進入編輯模式
   - 查看 AI 生成的訪談問題
   - 調整問題順序和重要性

3. **開始練習訪談**
   - 點擊「開始訪談」按鈕
   - 允許麥克風權限
   - 開始說話，觀察即時轉錄和評估

4. **查看訪談報告**
   - 結束訪談後查看充分度報告
   - 檢視每個問題的回答證據
   - 匯出報告（JSON 或 PDF）

---

## 🔗 相關資源

- **完整文檔**: `docs/README.md`
- **架構說明**: `docs/architecture/InsightGuide_開發架構書.md`
- **實施總結**: `IMPLEMENTATION_SUMMARY.md`
- **API 文件**: http://localhost:8001/docs（啟動後）

---

## 🆘 獲取幫助

如果遇到問題：

1. 查看 `./insightguide.sh logs` 的日誌輸出
2. 檢查 `docs/guides/` 中的詳細指南
3. 查看 GitHub Issues（如果已建立）
4. 檢查 `IMPLEMENTATION_SUMMARY.md` 中的已知限制

---

## 🎉 享受使用 InsightGuide！

您現在已經準備好開始使用 InsightGuide 進行需求訪談了。

祝您訪談順利！ 🚀
