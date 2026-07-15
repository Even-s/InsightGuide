# InsightGuide 全系統功能測試計劃

版本：1.0

建立日期：2026-07-14

適用範圍：InsightGuide v0.2.x 現行前端、後端、背景任務與外部整合

## 1. 測試目標

本計劃驗證使用者能從建立專案一路完成訪談規劃、受訪者指派、訪談大綱、即時訪談、訪談後分析、證據整合與 BRD 匯出，並涵蓋服務啟停、管理後台、失敗復原和資料一致性。

本文件是功能測試的主清單；效能、滲透測試與 AI 內容品質評分只定義最低驗收門檻，不取代專門的壓力測試、安全測試或模型評測。

## 2. 現況基線

- 前端目前使用 Vitest + Testing Library，共 11 個測試檔；本次盤點執行結果為 48 項通過。
- 後端使用 pytest；設定 `DEBUG=false` 後可收集並通過 347 項測試（另有 24 個 deprecation warnings）。
- 直接使用目前 `.env` 執行後端測試時，`DEBUG=release` 無法解析為布林值，會在測試收集階段失敗。此問題列為 M0 阻塞項。
- 目前沒有 Playwright/Cypress 等瀏覽器端 E2E 測試，也沒有現行 `.github/workflows` 工作流程。
- OpenAI、Realtime WebRTC、MinIO、Redis 與 Celery 都是功能旅程的一部分，測試時需要區分 mock 與真實整合環境。

## 3. 優先級與測試層級

| 等級 | 定義 | 執行時機 |
|---|---|---|
| P0 | 服務可用性、資料不遺失、核心旅程與高風險錯誤處理 | 每次提交與發版前 |
| P1 | 主要功能、常見例外、跨頁資料一致性 | 每日回歸與發版前 |
| P2 | 邊界條件、相容性、低頻管理功能與真實 AI 品質 | 每週或發版前 |

| 層級 | 工具建議 | 用途 |
|---|---|---|
| Service/API | pytest、FastAPI TestClient、測試 DB | 驗證規則、狀態轉換、API contract 與資料一致性 |
| Component | Vitest、Testing Library、MSW 或 Axios mock | 驗證表單、顯示狀態、按鈕與錯誤處理 |
| Browser E2E | Playwright | 驗證跨頁核心旅程、下載、權限與瀏覽器狀態 |
| Integration | Docker Compose、真實 PostgreSQL/Redis/MinIO/Celery | 驗證背景任務、SSE、檔案與跨服務流程 |
| Live acceptance | Chrome、真實麥克風、受控 OpenAI key | 驗證 WebRTC、語音品質與 AI 結果可用性 |

自動化欄位縮寫：`API`、`UNIT`、`E2E`、`INT`（整合）、`MANUAL`（人工）、`LIVE`（真實外部服務）。

## 4. 測試環境與資料

### 4.1 環境

1. `CI`：獨立 PostgreSQL、Redis、MinIO；OpenAI 全部 mock；每次執行清空資料。
2. `Integration`：完整 Docker Compose + Celery，使用固定檔案與固定 AI 回應。
3. `Staging Live`：真實 OpenAI/Realtime、Chrome 麥克風權限與測試專用 API key；不得使用正式資料。
4. `macOS Clean Install`：未安裝相依套件的新使用者環境，用於安裝器與 `.command` 驗收。

### 4.2 標準資料集

| 資料代號 | 內容 |
|---|---|
| TD-00 | 空資料庫，只有 `user_default` |
| TD-01 | 「診所網上預約掛號系統」專案，含名稱與完整描述 |
| TD-02 | TD-01 + 4 個角色槽位：使用者、管理、工程、決策者 |
| TD-03 | TD-02 + 3 位受訪者，其中一位無法受訪、一位已完成 |
| TD-04 | 已產生訪談大綱，含 3 個主題與 10 張問題卡 |
| TD-05 | 進行中的訪談，含 pending/listening/probably_sufficient/sufficient 卡片 |
| TD-06 | 已結束訪談，含 Realtime transcript、卡片狀態、Insight Memo 與 Round Aggregate |
| TD-07 | 3 場跨角色訪談，包含一致證據、單一來源、缺驗證角色與互相衝突證據 |
| TD-08 | PDF、DOCX、Markdown、空檔、錯誤格式與超大檔案 fixtures |
| TD-09 | OpenAI 逾時、429、5xx、空回應、格式錯誤；Redis/MinIO/Celery 中斷 fixtures |

## 5. 功能測試案例

### A. 安裝、啟停與導覽

| ID | P | 測試情境 | 前置條件與步驟摘要 | 預期結果 | 自動化 |
|---|---|---|---|---|---|
| SYS-001 | P0 | 新 Mac 一鍵安裝 | 乾淨 macOS；執行 `InstallInsightGuide.command` | Homebrew、Node、Python 3.11、Docker Desktop 與專案依賴安裝完成；重跑不破壞既有環境 | MANUAL |
| SYS-002 | P0 | 一鍵啟動全部服務 | 執行 `InsightGuide.command` 或 `./insightguide.sh launch` | PostgreSQL、Redis、MinIO、後端、Celery、前端皆 ready；瀏覽器開啟首頁 | INT |
| SYS-003 | P1 | 重複啟動 | 服務已運行，再執行 `start` | 不建立重複程序、不占用新 port，狀態仍為 healthy | INT |
| SYS-004 | P0 | 狀態與健康檢查 | 執行 `./insightguide.sh status`，呼叫 `/health` | 顯示各服務狀態；後端回傳 `healthy` 和正確環境 | INT |
| SYS-005 | P1 | 單一服務重啟 | 分別重啟 backend、celery、frontend | 指定服務重新啟動，其他服務不中斷，健康檢查恢復 | INT |
| SYS-006 | P0 | 一鍵關閉 | 執行 `StopInsightGuide.command` 或 `stop` | 專案服務停止且 PID 清理；不得停止無關程序 | INT |
| SYS-007 | P1 | 基礎依賴中斷 | 分別停止 DB、Redis、MinIO、Celery 後操作相關功能 | UI/API 顯示可理解錯誤，不假裝成功；服務恢復後可重試 | INT |
| SYS-008 | P0 | 設定值驗證 | 使用非法 `DEBUG=release` 啟動測試或服務 | 啟動腳本應提前指出非法值，測試環境使用明確 `DEBUG=false` | API |
| NAV-001 | P0 | 首頁入口 | 開啟 `/`，點「新建專案」與「管理專案」 | 分別到 `/projects/new`、`/projects`，回首頁按鈕一致可用 | E2E |
| NAV-002 | P1 | 直接網址與重新整理 | 直接開啟每個 React route 並重新整理 | Vite history fallback 正常，不出現伺服器 404 | E2E |
| NAV-003 | P1 | 無效資源 ID | 以不存在的 project/document/session ID 開頁 | 顯示錯誤或空狀態與返回入口，不停留無限 loading | E2E/API |
| NAV-004 | P2 | 未知前端路徑 | 開啟 `/not-found` | 顯示 404/返回首頁頁面，不是空白畫面 | E2E |

### B. 專案建立與專案管理

| ID | P | 測試情境 | 前置條件與步驟摘要 | 預期結果 | 自動化 |
|---|---|---|---|---|---|
| PRJ-001 | P0 | 必填驗證 | 名稱或描述為空、只有空白時嘗試建立 | 建立按鈕停用；不送 API | UNIT/E2E |
| PRJ-002 | P0 | 手動建立專案 | TD-00；輸入中文名稱及完整描述後建立 | 只建立一筆專案並導向詳情頁；輸入被 trim；開始產生訪談計劃 | API/E2E |
| PRJ-003 | P1 | 防止重複提交 | 建立時連點或按 Enter 多次 | loading 期間不可再送出；只有一筆專案 | E2E/API |
| PRJ-004 | P1 | 建立失敗保留內容 | 模擬 API 4xx/5xx/網路中斷 | 顯示錯誤；名稱與描述保留，可直接重試 | UNIT/E2E |
| PRJ-005 | P1 | 語音建立成功 | 允許麥克風，口述名稱、領域、目標、不包含範圍 | 名稱與描述正確填入；使用者確認後才建立 | E2E/LIVE |
| PRJ-006 | P1 | 語音權限與短錄音 | 拒絕權限；錄音小於 1000 bytes；不支援 MediaRecorder | 顯示對應訊息，表單仍可手動輸入，音軌確實釋放 | UNIT/E2E |
| PRJ-007 | P1 | 語音 AI 失敗 | 模擬 transcription/parse 逾時、空 transcript、502 | 顯示可重試錯誤；不覆蓋既有欄位 | API/UNIT |
| PRJ-008 | P0 | 專案清單與統計 | TD-00、TD-03 分別開 `/projects` | 空狀態正確；卡片顯示名稱、狀態、進度、受訪者數及最近訪談 | API/E2E |
| PRJ-009 | P1 | 近期專案 | 至少 6 個專案；開新建頁 | 只顯示最近 5 筆；點擊可進入正確專案 | UNIT/E2E |
| PRJ-010 | P0 | 刪除專案取消 | 點刪除後取消確認 | 專案與所有資料不變 | E2E |
| PRJ-011 | P0 | 刪除專案確認 | 建立含角色、受訪者、訪談的專案後確認刪除 | 清單移除；關聯資料依資料模型正確 cascade 或被拒絕，不留孤兒資料 | API/E2E |
| PRJ-012 | P1 | 專案 API contract | create/list/get/update/delete 使用有效與不存在 ID | 回應 schema 一致；不存在資源為 404；驗證錯誤為 422/400 | API |

### C. 訪談計劃與角色槽位

| ID | P | 測試情境 | 前置條件與步驟摘要 | 預期結果 | 自動化 |
|---|---|---|---|---|---|
| PLN-001 | P0 | 初始計劃品質與數量彈性 | 建立 TD-01 | 角色與專案領域相關；角色數由需求決定，不被固定最多 3 個；每個角色具目的、預期資訊、問題與優先級 | API/LIVE |
| PLN-002 | P1 | AI 格式失敗 fallback | 模擬 AI 回傳無效 JSON | 顯示暫用角色與說明；`generation_source=fallback`，不得冒充 AI 建議 | API/E2E |
| PLN-003 | P0 | 重新生成計劃 | 具 AI/fallback 與 user_created 角色後重生 | 只替換 AI/fallback 角色，保留使用者新增角色；順序與統計更新 | API/E2E |
| PLN-004 | P0 | 儀表板統計 | TD-02、TD-03 | 計劃進度、完成訪談、角色覆蓋、第一輪統計與後端一致 | API/E2E |
| PLN-005 | P1 | 建議下一步 | 存在未安排必要角色 | 顯示正確角色與原因；點擊直接開啟該角色的指派視窗 | UNIT/E2E |
| PLN-006 | P1 | 詳情展開與收合 | 點「詳情」後再收合 | 高度及透明度平滑進出；目的／資訊／問題收合；已指派受訪者始終顯示 | UNIT/E2E |
| PLN-007 | P0 | 分區編輯重要性 | 只修改 required/recommended/optional | 只更新 priority，其他欄位不變；卡片標籤立即同步 | API/E2E |
| PLN-008 | P0 | 分區編輯訪談目的 | 修改、取消、儲存 rationale | 取消不送出；儲存後刷新仍存在；其他欄位不被舊值覆蓋 | API/E2E |
| PLN-009 | P0 | 分區編輯預期資訊 | 以逗號輸入、含空白與空項 | 正確 trim、移除空項並持久化；問題與目的不變 | API/E2E |
| PLN-010 | P0 | 分區編輯關鍵問題 | 每行一題，含空行 | 正確分行、移除空行、順序保留；其他欄位不變 | API/E2E |
| PLN-011 | P1 | 同時編輯衝突 | 兩個分頁分別修改不同區塊後依序儲存 | 不應因完整物件 PUT 而互相覆蓋；若採 last-write-wins 必須提示版本衝突 | API/E2E |
| PLN-012 | P0 | 手動新增角色 | 填入類型、重要性、場次、第一輪、目的、資訊、問題 | 新卡片欄位與新增表單一致，來源為 user_created，統計更新 | API/E2E |
| PLN-013 | P1 | 新增角色邊界值 | 名稱空白；最低場次 0、1、20、21 | 名稱必填；場次限制 1–20；錯誤不建立資料 | UNIT/API |
| PLN-014 | P1 | 角色口說填入 | 口述完整角色資訊 | 只填草稿、不自動儲存；欄位、陣列與第一輪建議正確 | API/E2E/LIVE |
| PLN-015 | P1 | AI 補充／優化 | 名稱空白與有名稱各執行一次 | 空白時不可執行；成功時補足內容但保留明確輸入；失敗不清空草稿 | API/E2E |
| PLN-016 | P1 | 語音檔邊界 | 小於 1KB、超過 25MB、空 transcript、AI 5xx | 分別回傳 400/413/400/502 與可理解訊息 | API |
| PLN-017 | P0 | 上移下移與邊界 | 對首筆上移、末筆下移、中間項目移動 | 邊界按鈕停用；有效移動後刷新順序一致 | API/E2E |
| PLN-018 | P1 | 跳過與恢復 | 跳過未完成角色，再恢復 | 狀態、透明度、next action 與進度正確；completed 角色不可跳過 | API/E2E |
| PLN-019 | P0 | 刪除角色 | 刪除空角色及含受訪者角色 | 需有明確確認；關聯受訪者處理符合規則，不得產生孤兒 profile | API/E2E |
| PLN-020 | P1 | 角色不存在與跨專案 ID | 對不存在或其他專案 slot 執行更新／語音草稿 | 404/403，不可讀寫其他專案資料 | API |

### D. 受訪者與訪談大綱

| ID | P | 測試情境 | 前置條件與步驟摘要 | 預期結果 | 自動化 |
|---|---|---|---|---|---|
| PRO-001 | P0 | 手動新增受訪者 | 只填姓名；再填完整職稱、部門、類型、專長、不熟領域 | 姓名必填；完整資料正確儲存並出現在指定角色下 | API/E2E |
| PRO-002 | P1 | 陣列欄位解析 | 專長與不熟領域輸入含逗號、空白、重複值 | trim 並忽略空項；是否去重符合 API 規格 | API/UNIT |
| PRO-003 | P1 | 受訪者語音填入 | 口述姓名、職稱、部門、專長與界線 | 全欄位填入草稿，未辨識姓名時提示補填，不自動建立 | UNIT/E2E/LIVE |
| PRO-004 | P1 | 語音失敗與資源清理 | 權限拒絕、太短、不支援、API 失敗、錄音中關閉 | 顯示正確錯誤；停止所有 audio track；仍可手動輸入 | UNIT/E2E |
| PRO-005 | P0 | 指派狀態與統計 | 對同角色加入足量與不足量受訪者 | slot 狀態在 unassigned/partially_assigned/assigned 正確轉換；人數同步 | API/E2E |
| PRO-006 | P1 | 更新／取消／刪除受訪者 | 依序更新、標記 unavailable、刪除 | profile 與 slot 統計同步；已關聯訪談時遵守資料保護規則 | API |
| GDE-001 | P0 | 預設大綱設定 | 對受訪者開啟大綱設定 | 預設 30 分鐘；目的、重點、排除主題、風格可輸入 | UNIT/E2E |
| GDE-002 | P1 | 大綱語音合併 | 先填部分設定，再口述補充 | AI draft 與現有值合理合併，不清空未提及欄位，不自動生成 | UNIT/API/LIVE |
| GDE-003 | P1 | 大綱語音錯誤 | 無效 current_options、短檔、超大檔、空 transcript、502 | 保留原設定並顯示明確錯誤 | API/E2E |
| GDE-004 | P0 | 生成訪談大綱 | 使用 TD-03 受訪者與自訂設定生成 | 建立 document、themes/cards 與 guide；內容符合角色專長、知識界線及排除主題 | API/E2E/LIVE |
| GDE-005 | P1 | 重生訪談大綱 | 已有 guide 再生成 | 舊資料處理規則明確，不產生多個 UI 無法管理的有效 guide；狀態更新 | API/E2E |
| GDE-006 | P1 | 生成中關閉與連點 | 生成或語音分析時點關閉／連點生成 | 按鈕停用，不中斷成半成品、不重複建立 | UNIT/E2E |
| GDE-007 | P0 | 開始訪談選人 | 有多位受訪者，部分有 guide | 清單只顯示可訪談人員及 guide 狀態；選取正確 profile | UNIT/E2E |
| GDE-008 | P0 | 導向訪談 | 選擇 guide-ready 受訪者 | 導向正確 document，帶 projectId/stakeholderId；角色過濾可追溯 | E2E |

### E. 文件分析與準備模式

| ID | P | 測試情境 | 前置條件與步驟摘要 | 預期結果 | 自動化 |
|---|---|---|---|---|---|
| DOC-001 | P1 | 上傳支援格式 | 分別上傳 TD-08 PDF、DOCX、Markdown | 檔案存入 MinIO，Document 建立，檔名/MIME/狀態正確 | API/INT |
| DOC-002 | P1 | 非法、空白與超大檔案 | 上傳空檔、錯誤副檔名、超過限制檔案 | 拒絕並回傳明確狀態碼；MinIO/DB 不留半成品 | API/INT |
| DOC-003 | P0 | 從專案主題建立文件 | 由 guide 生成流程呼叫 `/documents/from-topic` | 建立的 document 綁定正確 project，進入 analysis 流程 | API |
| DOC-004 | P0 | Celery 分析成功 | 送出文件，worker 產生 themes/cards | 狀態依序更新，sections/themes/cards 完整，SSE 發出完成事件 | INT |
| DOC-005 | P1 | 分析失敗與重試 | 模擬轉檔、OpenAI、MinIO 或 worker 失敗 | 狀態為 failed 且保留原因；重試不建立重複主題／卡片 | INT |
| DOC-006 | P1 | 分析中頁面 | 開啟仍在 processing 的 document | 顯示進度並輪詢／接收事件；完成後自動載入，沒有無限 loading | E2E |
| EDT-001 | P0 | 準備模式載入 | TD-04 開啟 `/editor/:documentId` | 顯示訪談目標、主題順序、提問依據、BRD mapping 與問題數 | E2E |
| EDT-002 | P1 | 主題選擇 | 逐一點擊不同主題 | 右側內容與卡片切換正確，選取狀態明確 | E2E |
| EDT-003 | P0 | 新增與編輯問題卡 | 新增卡片，再修改問題、追問、優先級及規則 | API payload 正確，刷新後仍存在，未修改欄位不遺失 | API/E2E |
| EDT-004 | P0 | 刪除與排序問題卡 | 刪除一張；拖曳／操作重排 | 刪除需確認；排序連續且刷新後一致 | API/E2E |
| EDT-005 | P1 | 追問清理與重生 | 輸入冗長追問並執行 cleanup/regenerate | 回傳可用文字；失敗保留原內容 | API/E2E |
| EDT-006 | P1 | 生成 criteria／角色 targeting | 對卡片與全文件執行生成 | coverage criteria、semantic anchors、role targeting schema 完整 | API/LIVE |
| EDT-007 | P1 | 管理訪談側欄 | 無 session、進行中、暫停、已結束各測一次 | 顯示正確狀態、日期與可用操作；導向報告／繼續訪談正確 | E2E |
| EDT-008 | P0 | 開始訪談 | 從 editor 點開始 | 建立或取得正確 prep/session，進入 presenter，不重複建立 session | API/E2E |

### F. 即時訪談與卡片狀態

| ID | P | 測試情境 | 前置條件與步驟摘要 | 預期結果 | 自動化 |
|---|---|---|---|---|---|
| INT-001 | P0 | 建立與開始 session | TD-04 建立 session，按開始 | 狀態 idle/ready → interviewing；startedAt 只設定一次 | API/E2E |
| INT-002 | P0 | Realtime 連線成功 | 允許麥克風並取得 ephemeral session | WebRTC/DataChannel connected，顯示錄音中，音訊不經後端轉送 | E2E/LIVE |
| INT-003 | P0 | 麥克風或 token 失敗 | 拒絕權限；模擬 transcription-session 401/429/5xx | 不開始訪談或清楚顯示錯誤；可重試；不留下幽靈錄音 | E2E/API |
| INT-004 | P0 | SDP/ICE 連線異常 | 模擬 invalid_offer、ICE timeout、網路離線 | 顯示具體連線錯誤；既有 session 可安全重試／恢復 | E2E/LIVE |
| INT-005 | P0 | partial 與 completed transcript | 傳送多個 delta 再完成 utterance | pending 文字即時顯示；完成後只寫入一次歷史與後端 | UNIT/E2E |
| INT-006 | P1 | 中性逐字稿 | 連續輸入多段 Realtime transcript | 依時間保存完整內容，不產生訪問者／受訪者分類 | API/INT |
| INT-007 | P0 | 問題啟動卡片 | 訪談者問與特定卡片語意相符的問題 | 正確卡片 pending → listening；不誤啟動無關卡片 | API/INT |
| INT-008 | P0 | 部分回答 | 回答只覆蓋部分 criteria | 維持 listening 或 probably_sufficient；顯示缺口，不提前完成 | API/INT |
| INT-009 | P0 | 充分回答 | 回答具體覆蓋必要 criteria | 卡片轉 sufficient，保存 evidence/confidence，發出 SSE 事件 | API/INT |
| INT-010 | P1 | 否定、修正與矛盾回答 | 受訪者否定前述內容或更正數值 | 評估上下文採最新證據；不因關鍵字命中而錯誤完成 | API/INT |
| INT-011 | P1 | 多候選卡片 | 一句回答可能對應多張卡 | 顯示候選，選擇後 active card 正確；buffered answer 不遺失 | UNIT/E2E |
| INT-012 | P1 | 手動完成與復原 | 對卡片 manual complete，再 undo | 狀態與 manual override 正確持久化；SSE/UI 同步 | API/E2E |
| INT-013 | P1 | 追問佇列 | 產生多個追問並跳過第一個 | 顯示當前追問與佇列長度；跳過後進下一個，不重複 | UNIT/E2E |
| INT-014 | P1 | 主題前後切換 | 第一個、中央、最後一個主題操作導航 | 邊界按鈕停用；current theme/section 與後端一致 | API/E2E |
| INT-015 | P0 | 暫停與恢復 | 訪談中暫停，再恢復 | session interviewing ↔ paused；錄音／轉錄狀態一致，不重複計時 | API/E2E |
| INT-016 | P0 | 重新整理與續訪 | 進行中重新整理，或由 session URL 進入 | 載入原 session、current theme、卡片狀態與 transcript；不建立新 session | API/E2E |
| INT-017 | P1 | SSE 斷線重連 | 中斷 Redis/SSE 後恢復，傳送重複事件 | 自動重連；事件冪等，不重複更新卡片或 transcript | INT/E2E |
| INT-018 | P0 | 正常結束與 memo 聚合 | 有 Realtime transcript，按結束 | session ended；產生累積 memo；更新該輪 Aggregate | INT/E2E/LIVE |
| INT-019 | P0 | Realtime 寫入失敗 | 最後一段 transcript 儲存失敗 | 結束前等待或顯示錯誤；可重試且不誤產生 memo | UNIT/E2E |
| INT-020 | P1 | 重複結束與競態 | 雙擊結束、背景回應延遲、另一分頁同時結束 | end/memo/aggregate 冪等；Round Aggregate 只指向最新完成 memo | API/INT |

### G. 訪談後分析與報告

| ID | P | 測試情境 | 前置條件與步驟摘要 | 預期結果 | 自動化 |
|---|---|---|---|---|---|
| PST-001 | P0 | 結束後導向 | INT-018 成功 | 自動導向 `/sessions/:id/insight-memo`，不閃回訪談頁 | E2E |
| PST-002 | P0 | 產生 Insight Memo | TD-06 無 memo，點產生 | 建立痛點、需求線索、限制／假設、未解問題與下一步；可追溯 evidence | API/E2E |
| PST-003 | P1 | Memo 快取與重生 | 已有 memo 再開啟、再按重新產生 | 一般讀取不重複花費；重生規則明確並更新時間／內容 | API/E2E |
| PST-004 | P0 | 各場逐字稿分頁 | 切換同一輪不同 session | 每頁只顯示該場 Realtime transcript；內容不標 speaker | E2E |
| PST-005 | P1 | 累積洞察 | 同輪完成第二場續訪 | 最新 memo 與 Aggregate 納入兩場內容，專案輸出只計算一次 | API/E2E |
| PST-006 | P0 | 訪談報告生成 | 開啟 report route，等待 outputs generate | 顯示 BRD 與 transcript 分頁；失敗可重試；不無限 loading | API/E2E |
| PST-007 | P1 | 報告分析正確性 | TD-06 固定時間軸與卡片狀態 | 覆蓋率、時間軸、提問與語速統計符合 fixture | API |
| PST-008 | P1 | 下載 Markdown | 下載 BRD 與逐字稿 | 檔名、UTF-8、章節、證據與換行正確；檔案非空 | E2E |
| PST-009 | P1 | Session log | 依事件類型篩選並返回後台 | 摘要數與列表一致；篩選不改動資料；空狀態正確 | E2E/API |
| PST-010 | P1 | 背景後處理失敗 | Memo、Round Aggregate、Evidence Matrix 或 report 任一任務失敗 | 其他已完成產物仍可查看；失敗項可重試且不重複資料，失效狀態不會被誤標為 ready | INT |

### H. 證據矩陣與 BRD 準備度

| ID | P | 測試情境 | 前置條件與步驟摘要 | 預期結果 | 自動化 |
|---|---|---|---|---|---|
| EVD-001 | P1 | 無訪談資料 | TD-02 開啟矩陣 | 顯示尚無資料，不出錯；刷新有明確結果 | E2E |
| EVD-002 | P0 | 刷新矩陣 | TD-07 點刷新 | 每個 ready Round Aggregate 只提供一份最新累積 memo；據此建立候選需求並更新 summary，重跑冪等 | API/E2E |
| EVD-003 | P0 | 跨訪談去重 | 多位受訪者以不同措辭描述同需求 | 合併為同一 candidate，mention/source/evidence 全保留 | API |
| EVD-004 | P0 | 衝突與缺角色 | TD-07 | conflicted、needs_more_evidence、missing_validation_from 判定正確 | API/E2E |
| EVD-005 | P1 | 篩選與展開 | 逐一切換全部／已驗證／待補證／衝突／候選，展開項目 | 筆數與狀態一致；顯示來源角色、引文與衝突內容 | E2E |
| EVD-006 | P1 | 排除候選 | 點排除後刷新 | entry 為 rejected 且不再進入 BRD；刷新不復活，除非規格允許 | API/E2E |
| EVD-007 | P1 | 下一輪訪談建議 | 存在缺驗證角色與 evidence gap | 建議角色與問題對應缺口，可回到計劃安排訪談 | API |
| RDY-001 | P0 | 首次準備度檢查 | TD-02、TD-07 分別生成 | 建立 report，顯示總分、角色覆蓋、證據、衝突與建議 | API/E2E |
| RDY-002 | P0 | full/partial/not_ready | 使用三組固定 evidence fixtures | mode 與分數門檻一致；UI 文案和允許操作正確 | API/E2E |
| RDY-003 | P1 | 報告刷新 | 新增訪談／排除 evidence 後重算 | 新報告反映最新資料，舊報告可追溯或明確被取代 | API |
| RDY-004 | P1 | 缺少角色與衝突連結 | 報告存在 missing roles/conflicts | 可導向證據矩陣；顯示需要補訪談的角色與原因 | E2E |
| RDY-005 | P0 | BRD gate | 三種 readiness mode 嘗試生成專案 BRD | full 允許；partial 依規格警示／允許；not_ready 必須阻擋並說明 | API/E2E |

### I. BRD 生成與匯出

| ID | P | 測試情境 | 前置條件與步驟摘要 | 預期結果 | 自動化 |
|---|---|---|---|---|---|
| BRD-001 | P0 | 單次訪談生成 | TD-06 無 BRD，點生成 | 狀態 generating → completed；輪詢停止；只建立一份有效 draft | API/E2E |
| BRD-002 | P0 | 專案級生成 | TD-07 且 readiness full | BRD 只採正式證據，整合多角色來源並保存 project 關聯 | API/INT |
| BRD-003 | P0 | BRD 內容完整 | 檢查 completed BRD | 包含摘要、概述、目標、成功標準、需求、user story、驗收標準、假設、限制、風險 | API/E2E |
| BRD-004 | P1 | 生成失敗與重試 | 模擬 AI 429/5xx/格式錯誤/worker 中斷 | status failed、顯示 error；重試可成功，不留下永久 generating | API/INT |
| BRD-005 | P1 | 重新生成 | completed BRD 點重新生成 | 版本／覆蓋規則明確；不因輪詢建立多筆重複需求 | API/E2E |
| BRD-006 | P1 | 需求更新與刪除 API | patch priority/content，delete requirement | 回應與 BRD summary 一致；不存在 ID 為 404 | API |
| BRD-007 | P0 | Markdown 下載 | 下載 completed BRD | Content-Type、檔名、UTF-8、章節與資料正確 | API/E2E |
| BRD-008 | P0 | PDF 下載 | 下載並以瀏覽器或系統 PDF 閱讀器開啟 | HTTP 200、PDF 可開啟、中文字型正常、分頁無截斷、內容與 BRD 一致 | API/INT/MANUAL |

### J. 管理後台、驗證與通用錯誤

| ID | P | 測試情境 | 前置條件與步驟摘要 | 預期結果 | 自動化 |
|---|---|---|---|---|---|
| ADM-001 | P1 | 後台統計與階層 | TD-03、TD-06 開 `/prep-sessions` | 專案、受訪者、session、完成／進行／錯誤統計正確 | API/E2E |
| ADM-002 | P1 | 展開專案與受訪者 | 展開／收合各層 | 顯示 guide、session 完整 ID、狀態、時間、花費與可用操作 | E2E |
| ADM-003 | P0 | 強制結束 session | 對 interviewing session 執行強制結束 | 確認後狀態 ended；不可破壞已有 transcript；重跑冪等 | API/E2E |
| ADM-004 | P0 | 刪除 session／專案 | 取消一次、確認一次 | 取消不變；確認後列表與統計同步，關聯資料一致 | API/E2E |
| ADM-005 | P1 | 未歸屬 session | 建立無 project/profile session | 顯示於獨立區塊，仍可檢視 log、強制結束及刪除 | E2E |
| AUT-001 | P2 | 註冊、重複帳號 | 呼叫 register 兩次 | 首次成功；重複 email 被拒絕，不洩漏密碼 hash | API |
| AUT-002 | P2 | 登入與 `/me` | 正確／錯誤密碼、有效／過期／缺 token | 正確取得身份；錯誤為 401；不得以 token 存取他人資料 | API |
| AUT-003 | P0 | API 通用 contract | 測試 CORS、JSON error、422、404、非預期例外 | status code 與錯誤 schema 一致；production 不回傳 stack trace | API |

### K. 通用 UI、相容性與復原

| ID | P | 測試情境 | 前置條件與步驟摘要 | 預期結果 | 自動化 |
|---|---|---|---|---|---|
| UX-001 | P1 | 鍵盤操作 | 只用 Tab/Shift+Tab/Enter/Space 操作主流程 | 焦點順序合理；按鈕與選單可操作；焦點樣式可見 | E2E/MANUAL |
| UX-002 | P1 | Modal 焦點與關閉 | 開啟新增受訪者／大綱／開始訪談 modal | 焦點留在 modal；關閉後回原按鈕；背景不可誤點 | E2E |
| UX-003 | P1 | 動畫與減少動態 | 展開卡片、開關 modal、切頁；啟用 reduced motion | 一般模式淡入淡出滑順；reduced motion 幾乎立即完成且功能不變 | E2E/MANUAL |
| UX-004 | P1 | Responsive | 360px、768px、1440px 測主要頁面 | 無水平截斷；表單、卡片、操作按鈕可讀可點 | E2E |
| UX-005 | P2 | 瀏覽器相容 | 最新 Chrome、Safari；麥克風 MIME 能力不同 | 核心流程一致；不支援錄音時有文字輸入 fallback | MANUAL/LIVE |
| UX-006 | P0 | Loading 與重複操作 | 對慢 API、背景任務、下載操作連點 | 顯示 loading；危險／提交按鈕停用；不重複寫入 | UNIT/E2E |
| UX-007 | P0 | API 中斷復原 | 操作中斷網、恢復後重試／刷新 | 已儲存資料不遺失；未完成操作不顯示成功；可安全重試 | E2E |
| UX-008 | P1 | 中文與特殊字元 | 名稱、描述、逐字稿含繁中、簡中、emoji、Markdown、HTML 字串 | 正確儲存與顯示；不執行 HTML/script；匯出不亂碼 | API/E2E |

## 6. 核心跨系統 E2E 旅程

以下案例不應只由單頁測試取代。

| ID | P | 旅程 | 驗收終點 |
|---|---|---|---|
| E2E-001 | P0 | 首頁 → 新建專案 → AI 訪談計劃 → 新增角色 → 指派受訪者 | 專案詳情的計劃、統計與受訪者資料一致 |
| E2E-002 | P0 | 受訪者 → 訪談大綱 → 編輯問題卡 → 開始訪談 | 進入正確 session，角色過濾後的卡片可使用 |
| E2E-003 | P0 | 即時提問 → partial answer → sufficient answer → 暫停／恢復 → 結束 | 卡片狀態、Realtime transcript、session lifecycle 全部一致 |
| E2E-004 | P0 | 結束訪談 → Insight Memo → Round Aggregate → 報告 → Markdown/PDF | 產物可追溯至各場 Realtime transcript，下載檔可開啟 |
| E2E-005 | P0 | 三角色多場訪談 → Evidence Matrix → Readiness → 專案 BRD | 去重、衝突、缺口、gate 與最終 BRD 一致 |
| E2E-006 | P1 | 語音建立專案 → 語音新增角色 → 語音新增受訪者 → 語音設定大綱 | 每一步都先產生可人工確認的草稿，未確認前不寫入 |
| E2E-007 | P1 | Realtime 斷線 → 重連 → 續訪 → 重複結束請求 | 不遺失、不重複 transcript/evidence，session 可正確完成 |

## 7. AI 與語音驗收規則

一般 CI 不直接評斷自由生成文字是否「好看」，而使用固定回應驗證 schema 與資料流。真實 AI 驗收另外執行：

1. 每個 AI endpoint 至少覆蓋成功、空回應、格式錯誤、429、5xx、timeout。
2. 所有 AI 輔助填寫都只更新草稿，未經使用者確認不得直接寫入正式資料。
3. Stakeholder Plan 不使用固定最多角色數，需以需求範圍決定，且不得產生「只有他們能」等排他、空泛理由。
4. 問題卡必須可追溯至訪談目的／主題；BRD 需求必須可追溯至正式逐字稿或 evidence matrix。
5. Live 測試使用固定 10 段中文音訊與預期語意，不要求逐字完全相同，但姓名、角色、數值、否定與限制不得反轉。
6. 每次 Live 執行記錄 model、prompt version、latency、token/audio cost 與結果摘要。

## 8. 自動化里程碑

### M0 — 讓測試可穩定執行

- 新增 `backend/.env.test` 或 pytest fixture，強制 `DEBUG=false`、測試 DB 與假 OpenAI key。
- 取消測試對開發者 `.env` 的依賴。
- 建立 DB reset、MinIO bucket reset、Redis flush 與固定時間 fixture。
- 清理現有 React `act(...)` 與 React Router future flag 警告。

完成條件：後端 347 項可穩定收集；前端測試無非預期 warning。

### M1 — P0 API 與資料一致性

- 優先完成 PRJ、PLN、PRO、GDE、session lifecycle、card controls、EVD、RDY、BRD P0。
- 所有外部 AI 呼叫使用 contract mock；PostgreSQL 使用獨立測試資料庫。

完成條件：P0 API 測試全綠，重複請求與跨專案 ID 不造成資料污染。

### M2 — 前端元件與頁面整合

- 補齊建立專案、ProjectDetail、Editor、Presenter、Memo、Evidence、Readiness、BRD、Admin 測試。
- 使用 MSW 或統一 Axios mock，覆蓋 loading、empty、success、error 四態。

完成條件：主要頁面狀態分支都有測試；表單驗證與錯誤復原不依賴真實後端。

### M3 — Playwright P0 E2E

- 建立 E2E-001～E2E-005。
- CI 使用 mock AI；瀏覽器使用預先載入資料與可重置 DB。
- 下載檔案需驗證檔名、MIME、大小與基本內容。

完成條件：核心旅程可在乾淨環境重跑三次無 flaky failure。

### M4 — Realtime、SSE 與背景任務

- Chromium 使用 fake audio fixture 驗證前端 WebRTC 狀態。
- Integration 環境驗證 Redis SSE、Celery、MinIO、Realtime transcript 與 worker retry。
- 另設少量真實 OpenAI nightly，不阻塞一般 PR。

完成條件：中斷與重試案例不造成遺失、重複或永久 processing。

### M5 — Release acceptance

- macOS clean install、Chrome/Safari、真實麥克風、真實 OpenAI、PDF 視覺檢查。
- 執行 P0 + P1、核心 E2E 與 live acceptance；確認沒有 Sev-1/Sev-2 未結缺陷。

## 9. 執行門檻

### 進入條件

- 測試版本、資料庫 migration 與環境變數已固定。
- 測試資料不含正式個資或真實醫療資料。
- 外部服務使用測試帳號，費用與 rate limit 已設定上限。

### 通過條件

- P0：100% 通過，不允許 flaky retry 後才過。
- P1：至少 98% 通過，失敗案例需有已確認缺陷與發版決策。
- P2：至少 95% 通過，不得包含資料遺失、安全或核心流程阻斷。
- API contract、migration、下載檔與跨頁 E2E 必須有測試證據。
- 發版前不得有 Sev-1/Sev-2 未解缺陷。

### 缺陷嚴重度

| 等級 | 定義 | 範例 |
|---|---|---|
| Sev-1 | 資料遺失、安全問題、系統不可用 | 刪錯專案、跨專案讀取、服務無法啟動 |
| Sev-2 | 核心旅程無法完成且無替代方案 | 無法開始／結束訪談、無法生成或下載 BRD |
| Sev-3 | 主要功能錯誤但有替代方案 | 語音失敗但可手動輸入、單一統計錯誤 |
| Sev-4 | 顯示、文案、低頻操作問題 | 動畫不一致、非關鍵欄位排版 |

## 10. 建議的每次提交驗證命令

```bash
cd backend
DEBUG=false venv/bin/python -m pytest -q

cd ../frontend
npm run test:run
npm run type-check
npm run lint
npm run build
```

導入 Playwright 後，再加入不依賴真實 OpenAI 的 P0 E2E suite。真實 AI、真實麥克風與 clean-install 測試只放在 nightly 或 release acceptance。
