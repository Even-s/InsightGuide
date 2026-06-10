# SlideCue Features Documentation

本目錄包含 SlideCue 各項功能的詳細文檔。

## 📋 功能清單

### ⭐ PrepSession - 準備模式架構
**文檔**: [PREP_SESSION.md](../knowledge/features/PREP_SESSION.md)
**狀態**: ✅ 已完成
**更新日期**: 2026-05-26

**簡介**:
兩層架構設計，將準備階段與實際簡報分離。一個準備單位可包含多次練習記錄，支援重複練習與進度追蹤。

**核心功能**:
- 自動創建 PrepSession（進入編輯模式時）
- 狀態自動管理（preparing → ready）
- 支援多次簡報記錄
- 可視化管理介面
- Cascade 刪除機制

**相關文檔**:
- 更新日誌: [../archive/CHANGELOG_PREP_SESSION.md](../archive/CHANGELOG_PREP_SESSION.md)
- 架構文檔: [../architecture/SlideCue_開發架構書.md](../architecture/SlideCue_開發架構書.md)

---

### 📤 Deck Upload & Analysis
**狀態**: ✅ 已完成  

**功能**:
- PPTX/PPT 檔案上傳
- 自動 PDF 轉換（LibreOffice）
- 投影片圖片提取（Poppler）
- AI 分析（目前使用設定中的 slide analysis model）
- Topic Card 生成

**相關 Milestones**:
- Milestone 1 - 檔案上傳（歷史 milestone 文件已整併）
- [Milestone 2](../milestones/MILESTONE_2_SUMMARY.md) - AI 分析

---

### ✏️ Editor Mode
**狀態**: ✅ 已完成

**功能**:
- 投影片預覽
- Topic Card 管理
- 拖放排序
- 重要性設定
- 建議講稿編輯

**相關 Milestones**:
- Milestone 3 - 編輯器實作（歷史 milestone 文件已整併）

---

### 🎤 Presenter Mode with Realtime Transcription
**狀態**: ✅ 已完成

**功能**:
- WebRTC 即時語音轉錄
- OpenAI Realtime API 整合
- Topic Card 自動匹配
- 即時視覺回饋
- 語音活動檢測（VAD）

**相關 Milestones**:
- [Milestone 4](../milestones/MILESTONE_4_SUMMARY.md) - Realtime API 整合
- [Milestone 5](../milestones/MILESTONE_5_COMPLETE.md) - Matching Engine

---

### 📊 Session Reports
**狀態**: ✅ 核心完成

**功能**:
- 簡報後分析
- 覆蓋率報告
- 證據轉錄
- 效能洞察
- 匯出功能

**相關 Milestones**:
- [Milestone 7](../milestones/MILESTONE_7_SUMMARY.md) - 報告生成

---

## 📊 功能開發狀態

| 功能 | 狀態 | 完成度 | 相關文檔 |
|------|------|--------|----------|
| PrepSession 架構 | ✅ 完成 | 100% | [PREP_SESSION.md](../knowledge/features/PREP_SESSION.md) |
| 檔案上傳 | ✅ 完成 | 100% | Milestone 1 |
| AI 分析 | ✅ 完成 | 100% | Milestone 2 |
| 編輯器 | ✅ 完成 | 100% | Milestone 3 |
| Realtime 轉錄 | ✅ 完成 | 100% | Milestone 4 |
| Topic Matching | ✅ 完成 | 100% | Milestone 5 |
| Presenter UI | ✅ 完成 | 100% | Milestone 6 |
| 報告生成 | ✅ 核心完成 | 80%+ | Milestone 7 |

---

## 🎯 即將推出

### 🔄 Session Comparison
**優先級**: High  
**預計**: Q2 2026

比較同一 PrepSession 下的多次簡報記錄，追蹤改進趨勢。

### 📈 Practice Analytics
**優先級**: Medium  
**預計**: Q2 2026

統計圖表顯示練習次數、覆蓋率改善、時間分布等。

### 🏷️ PrepSession Tags & Filters
**優先級**: Low  
**預計**: Q3 2026

為 PrepSession 添加標籤和進階篩選功能。

---

## 📝 文檔規範

每個功能文檔應包含：

1. **概述** - 功能簡介、使用場景
2. **架構設計** - 資料模型、系統架構
3. **實作細節** - 程式碼範例、關鍵邏輯
4. **API 規格** - 端點、參數、回應格式
5. **使用指南** - 使用者操作流程
6. **測試** - 測試流程、測試案例
7. **故障排查** - 常見問題、解決方案
8. **參考資料** - 相關文檔、程式碼連結

---

**最後更新**: 2026-06-02
**維護者**: SlideCue Team
