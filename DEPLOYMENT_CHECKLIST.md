# InsightGuide 部署檢查清單

本文檔提供 InsightGuide 從開發環境到生產環境的完整部署檢查清單。

**最後更新**: 2026-06-09  
**版本**: v0.1.0

---

## 📋 部署前檢查

### 1. 程式碼品質 ✅

- [x] 所有 Phase 1-4 功能已完成
- [ ] 執行後端測試套件
- [ ] 執行前端測試套件
- [ ] 程式碼審查完成
- [ ] 移除 debug 程式碼和 console.log
- [ ] 確認沒有 TODO 或 FIXME 標記

### 2. 環境配置 ⏳

#### 後端環境變數（backend/.env）

必要配置：
- [ ] `OPENAI_API_KEY` - OpenAI API 金鑰
- [ ] `DATABASE_URL` - PostgreSQL 連接字串
- [ ] `REDIS_URL` - Redis 連接字串
- [ ] `S3_ENDPOINT_URL` - S3 endpoint（生產環境）
- [ ] `S3_ACCESS_KEY` - S3 access key
- [ ] `S3_SECRET_KEY` - S3 secret key
- [ ] `S3_BUCKET_NAME` - S3 bucket 名稱
- [ ] `SECRET_KEY` - JWT secret key（生成強密碼）
- [ ] `ENVIRONMENT` - 設定為 `production`

可選配置：
- [ ] `SENTRY_DSN` - Sentry 錯誤追蹤（建議）
- [ ] `LOG_LEVEL` - 日誌等級（建議 `INFO`）
- [ ] `CORS_ORIGINS` - CORS 允許的來源
- [ ] `MAX_UPLOAD_SIZE` - 最大上傳檔案大小

#### 前端環境變數（frontend/.env）

- [ ] `VITE_API_BASE_URL` - 後端 API URL
- [ ] `VITE_ENVIRONMENT` - 設定為 `production`

### 3. 資料庫 ⏳

- [ ] PostgreSQL 16+ 已安裝
- [ ] pgvector extension 已啟用
- [ ] 執行所有 Alembic migrations
- [ ] 資料庫備份策略已建立
- [ ] 資料庫連接池配置適當
- [ ] 索引已建立並優化

檢查指令：
```bash
cd backend
alembic current  # 確認目前版本
alembic history  # 查看 migration 歷史
```

### 4. 依賴套件 ⏳

#### 後端依賴
```bash
cd backend
pip install -r requirements.txt
```

檢查：
- [ ] 所有 Python 套件已安裝
- [ ] 版本與 requirements.txt 一致
- [ ] 沒有安全漏洞（使用 `pip audit`）

#### 前端依賴
```bash
cd frontend
npm install
npm audit fix  # 修復安全漏洞
```

檢查：
- [ ] 所有 npm 套件已安裝
- [ ] 版本與 package.json 一致
- [ ] 沒有高危漏洞

### 5. 建置測試 ⏳

#### 後端
```bash
cd backend
python -m pytest  # 執行測試（如果有）
uvicorn app.main:app --host 0.0.0.0 --port 8001  # 測試啟動
```

#### 前端
```bash
cd frontend
npm run build  # 建置生產版本
npm run preview  # 預覽建置結果
```

檢查：
- [ ] 建置無錯誤
- [ ] 建置產物大小合理
- [ ] 沒有未使用的依賴

---

## 🚀 部署步驟

### 階段 1: 基礎設施準備

#### 1.1 伺服器準備
- [ ] 生產伺服器已準備（雲端或自架）
- [ ] 防火牆規則已配置
- [ ] SSL 證書已準備（HTTPS）
- [ ] 網域名稱已配置
- [ ] 負載平衡器已設定（如需要）

#### 1.2 Docker 環境
```bash
# 安裝 Docker 和 Docker Compose
docker --version
docker-compose --version

# 確認 Docker 已啟動
docker ps
```

#### 1.3 資料庫設定
```bash
# 啟動 PostgreSQL（使用 Docker 或雲端服務）
docker-compose -f docker-compose.prod.yml up -d postgres

# 建立資料庫
docker exec -it postgres psql -U postgres
CREATE DATABASE insightguide;
CREATE EXTENSION vector;
\q

# 執行 migrations
cd backend
alembic upgrade head
```

#### 1.4 Redis 設定
```bash
# 啟動 Redis（使用 Docker 或雲端服務）
docker-compose -f docker-compose.prod.yml up -d redis

# 測試連接
redis-cli ping
```

#### 1.5 S3 儲存設定
- [ ] S3 bucket 已建立
- [ ] CORS 規則已配置
- [ ] IAM 權限已設定
- [ ] 測試檔案上傳和下載

### 階段 2: 應用程式部署

#### 2.1 後端部署

選項 A: Docker 部署（推薦）
```bash
# 建置 Docker image
cd backend
docker build -t insightguide-backend:v0.1.0 .

# 執行容器
docker run -d \
  --name insightguide-backend \
  -p 8001:8001 \
  --env-file .env \
  insightguide-backend:v0.1.0
```

選項 B: 直接部署
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8001
```

#### 2.2 Celery Worker 部署
```bash
# 啟動 Celery worker
celery -A app.workers.celery_app worker \
  --loglevel=info \
  --concurrency=4 \
  --max-tasks-per-child=1000
```

使用 Supervisor 或 systemd 管理 Celery：
```ini
# /etc/supervisor/conf.d/celery.conf
[program:celery-worker]
command=/path/to/venv/bin/celery -A app.workers.celery_app worker --loglevel=info
directory=/path/to/backend
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
```

#### 2.3 前端部署

建置前端：
```bash
cd frontend
npm install
npm run build
```

選項 A: Nginx 部署（推薦）
```nginx
# /etc/nginx/sites-available/insightguide
server {
    listen 80;
    server_name insightguide.yourdomain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name insightguide.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    root /path/to/frontend/dist;
    index index.html;

    # Frontend routes
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API requests
    location /api/ {
        proxy_pass http://localhost:8001/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support for Realtime API
    location /ws/ {
        proxy_pass http://localhost:8001/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

選項 B: CDN 部署
- [ ] 上傳 dist/ 到 CDN（Cloudflare、AWS CloudFront 等）
- [ ] 配置快取規則
- [ ] 設定 API proxy

### 階段 3: 監控與日誌

#### 3.1 應用程式監控
- [ ] Sentry 已配置（錯誤追蹤）
- [ ] 健康檢查 endpoint 已驗證（`/health`）
- [ ] Uptime 監控已設定（Pingdom、UptimeRobot 等）
- [ ] 效能監控已設定（New Relic、DataDog 等）

#### 3.2 日誌管理
```bash
# 配置日誌輪替
# /etc/logrotate.d/insightguide
/var/log/insightguide/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0644 www-data www-data
    sharedscripts
}
```

- [ ] 應用程式日誌已集中收集
- [ ] 日誌輪替已配置
- [ ] 日誌搜尋已設定（ELK Stack、Splunk 等）

#### 3.3 效能監控
- [ ] 資料庫查詢效能監控
- [ ] API 回應時間監控
- [ ] Celery 任務佇列監控
- [ ] 記憶體和 CPU 使用率監控

---

## ✅ 部署後驗證

### 1. 功能測試

#### 1.1 基本功能
- [ ] 首頁載入正常
- [ ] 可以註冊/登入（如有實作）
- [ ] API 健康檢查正常（`/health`）
- [ ] API 文件可存取（`/docs`）

#### 1.2 文件上傳
- [ ] 可以上傳 PDF 文件
- [ ] 可以上傳 DOCX 文件
- [ ] 可以上傳 Markdown 文件
- [ ] 文件分析工作正常執行
- [ ] 分析進度即時更新（SSE）

#### 1.3 問題卡片
- [ ] 問題卡片自動生成
- [ ] 可以編輯問題卡片
- [ ] 可以重新排序卡片
- [ ] 可以刪除卡片
- [ ] 可以重新生成追問

#### 1.4 訪談模式
- [ ] 可以開始訪談
- [ ] 麥克風權限請求正常
- [ ] 即時轉錄功能正常
- [ ] 回答評估即時更新
- [ ] 卡片狀態變化正常
- [ ] 可以暫停/繼續訪談
- [ ] 可以結束訪談

#### 1.5 報告生成
- [ ] 訪談報告自動生成
- [ ] 報告內容完整
- [ ] 可以匯出 JSON
- [ ] 可以匯出 PDF（如有實作）

### 2. 效能測試

```bash
# API 回應時間測試
curl -w "@curl-format.txt" -o /dev/null -s http://your-domain.com/health

# 負載測試（使用 Apache Bench）
ab -n 1000 -c 10 http://your-domain.com/api/documents/
```

檢查：
- [ ] API 平均回應時間 < 200ms
- [ ] 95th percentile < 500ms
- [ ] 並發請求處理正常
- [ ] 沒有記憶體洩漏

### 3. 安全測試

- [ ] HTTPS 已啟用
- [ ] SSL 證書有效
- [ ] CORS 設定正確
- [ ] API 認證正常（如有實作）
- [ ] 敏感資料已加密
- [ ] SQL injection 防護
- [ ] XSS 防護
- [ ] CSRF 防護

### 4. 容錯測試

- [ ] 資料庫斷線後恢復
- [ ] Redis 斷線後恢復
- [ ] S3 暫時無法存取的處理
- [ ] OpenAI API 錯誤處理
- [ ] Celery worker 崩潰恢復

---

## 📊 監控指標

### 關鍵指標（KPIs）

#### 應用程式健康度
- API 可用性 > 99.9%
- 平均回應時間 < 200ms
- 錯誤率 < 0.1%

#### 使用者體驗
- 文件上傳成功率 > 98%
- 分析完成時間 < 2 分鐘
- 轉錄延遲 < 500ms

#### 資源使用
- CPU 使用率 < 70%
- 記憶體使用率 < 80%
- 磁碟使用率 < 80%

#### 成本控制
- OpenAI API 每日成本
- 資料庫儲存成本
- S3 儲存和流量成本

---

## 🔄 持續部署（CI/CD）

### 建議工具
- GitHub Actions
- GitLab CI/CD
- Jenkins
- CircleCI

### CI/CD Pipeline 範例

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: |
          cd backend
          pip install -r requirements.txt
          pytest

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build Docker images
        run: |
          docker build -t insightguide-backend:${{ github.sha }} backend/
          docker build -t insightguide-frontend:${{ github.sha }} frontend/

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to production
        run: |
          # 部署腳本
          ssh user@server 'docker-compose pull && docker-compose up -d'
```

---

## 🆘 回滾計畫

### 快速回滾步驟

1. **回滾 Docker 容器**
```bash
docker-compose down
docker-compose -f docker-compose.prod.yml up -d --scale backend=0
docker-compose -f docker-compose.prod.yml up -d insightguide-backend-previous
```

2. **回滾資料庫**
```bash
cd backend
alembic downgrade -1  # 回滾一個版本
```

3. **回滾前端**
```bash
# 切換到上一個版本的 dist
ln -sf /path/to/previous/dist /var/www/insightguide
nginx -s reload
```

---

## 📞 支援與聯絡

部署相關問題：
- 查看日誌: `./insightguide.sh logs`
- 查看文檔: `docs/`
- GitHub Issues（如已建立）

---

## ✅ 最終檢查清單

部署前最後確認：

- [ ] 所有環境變數已正確設定
- [ ] 資料庫 migrations 已執行
- [ ] SSL 證書已配置
- [ ] 備份策略已建立
- [ ] 監控已設定
- [ ] 錯誤追蹤已啟用
- [ ] 日誌管理已配置
- [ ] 所有功能測試通過
- [ ] 效能測試通過
- [ ] 安全測試通過
- [ ] 團隊已接受部署訓練
- [ ] 回滾計畫已準備

---

**部署完成！** 🎉

請持續監控系統狀態，並根據實際使用情況調整配置。

祝部署順利！
