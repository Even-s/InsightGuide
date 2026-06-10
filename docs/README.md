# InsightGuide 文檔

歡迎來到 InsightGuide 文檔中心。

## 📚 核心文檔

### 必讀文檔
1. **[README.md](../README.md)** - 專案概覽、技術棧、快速開始
2. **[InsightGuide_開發架構書.md](architecture/InsightGuide_開發架構書.md)** - 完整系統架構（主要文檔）
3. **[QUICKSTART.md](guides/QUICKSTART.md)** - 快速開始指南

## 🏗️ Architecture - 架構文檔

### 系統架構
- **[InsightGuide_開發架構書.md](architecture/InsightGuide_開發架構書.md)** ⭐ 主架構文檔
  - 產品定位與核心流程
  - 技術棧規範（React + FastAPI + WebRTC）
  - OpenAI Realtime Transcription API 架構
  - GPT-5.4-mini 語義理解
  - Answer Evaluation Engine（回答評估引擎）
  - 資料庫 Schema
  - API 設計
  - 部署架構

## 🎯 開發狀態

**最後更新**: 2026-06-09
**開發階段**: 架構設計與專案初始化
**基礎架構**: InsightGuide 需求訪談輔助系統

### 已完成
- ✅ 專案複製與清理
- ✅ 品牌識別更新
- ✅ 架構文檔設計

### 進行中
- 🟡 後端資料模型調整
- 🟡 前端組件重命名
- 🟡 AI 分析邏輯調整

### 待實作
- ⏳ Answer Evaluation Engine
- ⏳ BRD 文件生成功能
- ⏳ 完整端到端測試

## 📖 Guides - 開發指南

### 快速開始
- **[QUICKSTART.md](guides/QUICKSTART.md)** - 通用快速開始

## 🔍 核心概念對應

InsightGuide 基於 SlideCue 架構改造，核心概念對應如下：

| SlideCue | InsightGuide | 說明 |
|----------|--------------|------|
| Deck | Document | 需求文件 |
| Slide | Section | 文件章節 |
| Topic Card | Question Card | 訪談問題卡 |
| Presentation Session | Interview Session | 訪談場次 |
| Topic Matching | Answer Evaluation | 回答充分度評估 |

---

**文檔整理日期**: 2026-06-09
**整理者**: Claude Code
