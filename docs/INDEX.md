# InsightGuide 文檔完整索引

**最後更新**: 2026-06-02
**總文件數**: 137 個 Markdown / text 文件（不含 dependency docs 與 generated cache）

---

## 📚 核心文檔

### 必讀文檔
1. **[README.md](../README.md)** - 專案概覽、技術棧、快速開始
2. **[InsightGuide_開發架構書.md](architecture/InsightGuide_開發架構書.md)** - 完整系統架構（主要文檔）
3. **[Knowledge Base](knowledge/README.md)** ⭐ **新增** - AI、架構、前端、功能與設計知識庫
4. **[QUICKSTART.md](guides/QUICKSTART.md)** - 快速開始指南
5. **[PROJECT_STATUS.md](reports/PROJECT_STATUS.md)** - 當前專案狀態

### 最新更新 (2026-06-02) ⭐ NEW
- **[SYSTEM_HEALTH_CHECK_REPORT.md](reports/SYSTEM_HEALTH_CHECK_REPORT.md)** - 最新系統健康檢查、依賴關係審核與驗證命令
- **[HEALTH_CHECK_SUMMARY.md](reports/HEALTH_CHECK_SUMMARY.md)** - 健康檢查快速摘要
- **[MILESTONE_7_SUMMARY.md](milestones/MILESTONE_7_SUMMARY.md)** - Session Report 實作、測試狀態與後續工作
- **[REALTIME_MATCHING_AND_HALLUCINATION_FILTER.md](fixes/REALTIME_MATCHING_AND_HALLUCINATION_FILTER.md)** - GPT 語意匹配、Whisper 幻覺過濾與 Script Plan 404 診斷
- **[FRONTEND.md](knowledge/frontend/FRONTEND.md)** - 前端現況、路由、Presenter Mode 與驗證命令
- **[guides/scripts/README.md](guides/scripts/README.md)** - scripts 說明已集中到 docs
- **[knowledge/README.md](knowledge/README.md)** - 知識型文件已集中到 knowledge

### 歷史更新 (2026-05-29)
- **[knowledge/ai/GPT-5.5-MODEL-GUIDE.md](knowledge/ai/GPT-5.5-MODEL-GUIDE.md)** - GPT-5.5 官方文檔整理
- **[RECONSTRUCTION_SUMMARY.md](archive/RECONSTRUCTION_SUMMARY.md)** - 程式碼重構歷史摘要
- **[ARCHITECTURE_DIAGRAM.md](architecture/ARCHITECTURE_DIAGRAM.md)** - 系統架構圖

### 歷史更新 (2026-05-26)
- 歷史修復與驗證報告已移至 [archive/](archive/)

---

## 🧠 Knowledge Base - 知識庫

穩定知識型文件集中於 `docs/knowledge/`，避免和歷史修復紀錄、milestone、report 混在一起。

- **[knowledge/README.md](knowledge/README.md)** - 知識庫入口
- **[AI / Models](knowledge/ai/GPT_MODEL_CONFIG.md)** - GPT 模型設定、模型選型與 realtime prompt 設計
- **[Architecture](knowledge/architecture/SESSION_MANAGEMENT_ARCHITECTURE.md)** - 子系統架構與資料流設計
- **[Frontend](knowledge/frontend/FRONTEND.md)** - 前端狀態、路由與驗證方式
- **[Features](knowledge/features/PREP_SESSION.md)** - Prep Session、SSE、Suggested Script 功能規格
- **[Design](knowledge/design/IMAGE_GUIDELINES.md)** - 圖像與視覺規範

---

## 🏗️ Architecture - 架構文檔

### 系統架構
- **[SlideCue_開發架構書.md](architecture/SlideCue_開發架構書.md)** ⭐ 主架構文檔
  - 產品定位與核心流程
  - 技術棧規範（React + FastAPI + WebRTC）
  - OpenAI Realtime Transcription API 架構
  - GPT-5.4-mini 語義理解
  - Topic Matching Engine（2階段匹配）
  - 資料庫 Schema
  - API 設計
  - 部署架構

---

## 🎯 Milestones - 里程碑文檔

### Milestone 2: AI Slide Analysis ✅ 完成
- [MILESTONE_2_SUMMARY.md](milestones/MILESTONE_2_SUMMARY.md) - M2 架構、實作、驗證與疑難排解整合版

### Milestone 4: Realtime Transcription ✅ 完成
- [MILESTONE_4_SUMMARY.md](milestones/MILESTONE_4_SUMMARY.md) - M4 Realtime Transcription 架構、狀態與歷史 Whisper 說明整合版

### Milestone 5: Topic Matching Engine ✅ 完成
- [MILESTONE_5_COMPLETE.md](milestones/MILESTONE_5_COMPLETE.md) - M5 完成報告

### Milestone 6: Presenter Mode UI ✅ 完成
- [MILESTONE_6_SUMMARY.md](milestones/MILESTONE_6_SUMMARY.md) - M6 計劃、實作狀態、完成報告與測試清單整合版

### Milestone 7: Session Report 🟡 核心完成
- [MILESTONE_7_SUMMARY.md](milestones/MILESTONE_7_SUMMARY.md) - M7 Session Report 實作、測試狀態與後續工作

---

## 📖 Guides - 開發指南

### 快速開始
- **[QUICKSTART.md](guides/QUICKSTART.md)** - 通用快速開始
- [QUICKSTART_M2.md](guides/QUICKSTART_M2.md) - Milestone 2 快速開始
- [DOCKER_SETUP.md](guides/DOCKER_SETUP.md) - Docker 環境設置
- [QUICK_REFERENCE.md](guides/QUICK_REFERENCE.md) - 快速參考

### 前端開發指南
- **[FRONTEND.md](knowledge/frontend/FRONTEND.md)** - 目前前端狀態、路由、驗證方式

### Scripts
- **[guides/scripts/README.md](guides/scripts/README.md)** - scripts 總覽
- **[INTEGRATION_TESTS.md](guides/scripts/INTEGRATION_TESTS.md)** - 手動 integration tests
- **[UTILITIES.md](guides/scripts/UTILITIES.md)** - utility scripts

### 測試指南
- [TESTING_GUIDE_M6.md](guides/TESTING_GUIDE_M6.md) - Milestone 6 測試指南

### 環境設置
- [POPPLER_INSTALLATION_GUIDE.md](guides/POPPLER_INSTALLATION_GUIDE.md) - Poppler 安裝指南（PDF 處理）

---

## 🔧 Fixes - 問題修復記錄

### 重要修復
- [REALTIME_MATCHING_AND_HALLUCINATION_FILTER.md](fixes/REALTIME_MATCHING_AND_HALLUCINATION_FILTER.md) - GPT 語意匹配與 Whisper 幻覺過濾整合記錄
- [TIMER_480_FINAL_FIX.md](fixes/TIMER_480_FINAL_FIX.md) - 計時器 480 小時問題最終修復
- [TIMER_BUG_FIX.md](fixes/TIMER_BUG_FIX.md) - 計時器錯誤修復
- [TIMER_480_EXPLANATION.md](fixes/TIMER_480_EXPLANATION.md) - 480 小時問題說明

### Bug 分析
- [BUG_ROOT_CAUSE.md](fixes/BUG_ROOT_CAUSE.md) - Bug 根本原因分析
- [DEBUG_STEPS.md](fixes/DEBUG_STEPS.md) - 除錯步驟
- [ISSUE_ANALYSIS_2026-05-25.md](fixes/ISSUE_ANALYSIS_2026-05-25.md) - 2026-05-25 問題分析

### 功能改進
- [CARD_SPACING_IMPROVEMENTS.md](fixes/CARD_SPACING_IMPROVEMENTS.md) - 卡片間距改進
- [SSE_IMPLEMENTATION.md](fixes/SSE_IMPLEMENTATION.md) - SSE 實作

### UI/UX 改進
- [DRAG_AND_DROP_CARDS.md](fixes/DRAG_AND_DROP_CARDS.md) - 拖放卡片功能
- [DRAG_HANDLE_ONLY.md](fixes/DRAG_HANDLE_ONLY.md) - 僅拖曳手柄
- [INLINE_CARD_EDITING.md](fixes/INLINE_CARD_EDITING.md) - 內聯卡片編輯
- [SWIPE_TO_RESET_FEATURE.md](fixes/SWIPE_TO_RESET_FEATURE.md) - 滑動重置功能
- [SWIPE_CLICK_DISTINCTION.md](fixes/SWIPE_CLICK_DISTINCTION.md) - 滑動/點擊區分
- [SWIPE_DELETE_CLOSE.md](fixes/SWIPE_DELETE_CLOSE.md) - 滑動刪除/關閉
- [PRESENTER_CARD_HIGHLIGHT_FEATURE.md](fixes/PRESENTER_CARD_HIGHLIGHT_FEATURE.md) - 演講者卡片高亮
- [PRESENTER_PERCENTAGE_DISPLAY.md](fixes/PRESENTER_PERCENTAGE_DISPLAY.md) - 演講者百分比顯示
- [PROGRESS_BAR_ALWAYS_VISIBLE.md](fixes/PROGRESS_BAR_ALWAYS_VISIBLE.md) - 進度條始終可見

### 編輯器改進
- [FIX_EDITOR_CARDS.md](fixes/FIX_EDITOR_CARDS.md) - 編輯器卡片修復
- [FIX_SUMMARY.md](fixes/FIX_SUMMARY.md) - 修復總結
- [FIXES_IMPLEMENTED.md](fixes/FIXES_IMPLEMENTED.md) - 已實作修復

### 新功能
- [BULLET_POINTS_FEATURE.md](fixes/BULLET_POINTS_FEATURE.md) - 項目符號功能

---

## 📊 Reports - 驗證報告

### 系統狀態
- **[SYSTEM_HEALTH_CHECK_REPORT.md](reports/SYSTEM_HEALTH_CHECK_REPORT.md)** - 最新系統健康檢查報告
- [PROJECT_STATUS.md](reports/PROJECT_STATUS.md) - 專案狀態與路線圖
- [HEALTH_CHECK_SUMMARY.md](reports/HEALTH_CHECK_SUMMARY.md) - 最新健康檢查總結

### 歷史報告
- 舊驗證報告、單次 deck 分析報告已移至 [archive/](archive/)

---

## 🗄️ Archive - 過時文檔

以下文檔已過時或被新版本取代，保留作為歷史參考：

- [CODE_VERIFICATION_REPORT_OLD.md](archive/CODE_VERIFICATION_REPORT_OLD.md) - 舊版驗證報告
- [CURRENT_STATUS.md](archive/CURRENT_STATUS.md) - 舊狀態報告
- [IMPLEMENTATION_STATUS.md](archive/IMPLEMENTATION_STATUS.md) - 舊實作狀態
- [SUCCESS_SUMMARY.md](archive/SUCCESS_SUMMARY.md) - 成功總結
- [SIMPLIFIED_EDITOR_COMPLETE.md](archive/SIMPLIFIED_EDITOR_COMPLETE.md) - 簡化編輯器完成
- [LAYOUT_REDESIGN.md](archive/LAYOUT_REDESIGN.md) - 布局重設計
- [SLIDE_PREVIEW_ENLARGEMENT.md](archive/SLIDE_PREVIEW_ENLARGEMENT.md) - 投影片預覽放大
- [QUICK_TEST_SSE.md](archive/QUICK_TEST_SSE.md) - SSE 快速測試
- [TEST_CARD_POLLING.md](archive/TEST_CARD_POLLING.md) - 卡片輪詢測試
- [TEST_MILESTONE_1.md](archive/TEST_MILESTONE_1.md) - Milestone 1 測試
- [TEST_WHISPER_API.md](archive/TEST_WHISPER_API.md) - Whisper API 測試

---

## 🔍 依主題查找

### 語音轉錄
- [SlideCue_開發架構書.md](architecture/SlideCue_開發架構書.md) - Realtime Transcription API 架構
- [MILESTONE_4_SUMMARY.md](milestones/MILESTONE_4_SUMMARY.md) - M4 完成狀態
- [REALTIME_MATCHING_AND_HALLUCINATION_FILTER.md](fixes/REALTIME_MATCHING_AND_HALLUCINATION_FILTER.md) - GPT 語意匹配與幻覺過濾

### 主題匹配
- [SlideCue_開發架構書.md](architecture/SlideCue_開發架構書.md) - Topic Matching Engine
- [MILESTONE_5_COMPLETE.md](milestones/MILESTONE_5_COMPLETE.md) - M5 完成報告
- [REALTIME_MATCHING_AND_HALLUCINATION_FILTER.md](fixes/REALTIME_MATCHING_AND_HALLUCINATION_FILTER.md) - GPT 語意匹配測試結果與權衡

### 智慧題詞 / Script Plan
- [SYSTEM_HEALTH_CHECK_REPORT.md](reports/SYSTEM_HEALTH_CHECK_REPORT.md) - 卡片與題詞依賴關係審核
- [SCRIPT_PLAN_PHASE2_COMPLETE.md](completed-features/SCRIPT_PLAN_PHASE2_COMPLETE.md) - Script Plan 里程碑記錄
- [SCRIPT_PLAN_LOGGING.md](guides/SCRIPT_PLAN_LOGGING.md) - Script Plan log 檢查指南

### 前端開發
- [FRONTEND.md](knowledge/frontend/FRONTEND.md) - 目前前端狀態
- [MILESTONE_6_SUMMARY.md](milestones/MILESTONE_6_SUMMARY.md) - M6 總結

### 測試與驗證
- [SYSTEM_HEALTH_CHECK_REPORT.md](reports/SYSTEM_HEALTH_CHECK_REPORT.md) - 健康檢查

---

## 📈 統計

- **總文件數**: 137 個 Markdown / text 文件（含 docs 內已整理文件）
- **架構文檔**: 1 個
- **里程碑文檔**: 18 個
- **開發指南**: 12 個
- **問題修復**: 34 個
- **當前報告**: 3 個
- **過時文檔**: 58 個
- **核心 README**: 1 個

---

**文檔整理日期**: 2026-06-02
**整理者**: Claude Code
