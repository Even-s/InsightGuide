# GPT-5.4 mini 模型文檔

> **來源**: https://developers.openai.com/api/docs/models/gpt-5.4-mini  
> **更新日期**: 2026-05-29

---

## 📋 基本資訊

**模型名稱**: GPT-5.4 mini

**定位**: OpenAI 最強大的迷你模型，專為以下場景設計：
- 🖥️ **編碼** (Coding)
- 💻 **計算機使用** (Computer Use)
- 🤖 **子代理** (Sub-agents)

**發布日期**: 2025年8月31日

---

## 🔧 核心規格

| 項目 | 規格 | 說明 |
|------|------|------|
| **上下文窗口** | 400,000 tokens | 可處理約 30 萬字的上下文 |
| **最大輸出令牌** | 128,000 tokens | 單次回應最多約 9.6 萬字 |
| **推理令牌** | ✅ 支持 | 支持思維鏈推理 |
| **知識截止** | 2025-08-31 | 訓練資料截至日期 |

---

## 💰 定價（每百萬令牌）

| 類型 | 價格 | 說明 |
|------|------|------|
| **輸入** | $0.75 | 基本輸入成本 |
| **緩存輸入** | $0.075 | 使用緩存時僅 10% |
| **輸出** | $4.50 | 生成的內容 |

> ⚠️ **注意**: 區域處理端點收取 **10% 溢價費用**

### 成本對比範例
```
100 萬輸入 tokens + 10 萬輸出 tokens:
= $0.75 + $0.45 = $1.20

使用緩存:
= $0.075 + $0.45 = $0.525 (節省 56%)
```

---

## 🎯 支持的模態

| 模態 | 輸入 | 輸出 | 說明 |
|------|------|------|------|
| **文本** | ✅ | ✅ | 完整支持 |
| **圖像** | ✅ | ❌ | 可理解圖片，但不能生成 |
| **音頻** | ❌ | ❌ | 不支持 |
| **視頻** | ❌ | ❌ | 不支持 |

---

## 🔌 API 端點支持

GPT-5.4 mini 支持以下 OpenAI API 端點：

- ✅ **Chat Completions** - 基本對話完成
- ✅ **Responses** - 回應生成
- ✅ **Realtime** - 即時串流
- ✅ **Batch** - 批次處理
- ✅ **Fine-tuning** - 微調訓練

---

## ⚡ 功能特性

### 核心功能
- **流式傳輸** (Streaming)
- **函數調用** (Function Calling)
- **結構化輸出** (Structured Output)

### 工具支持
- 🔍 **Web 搜索** - 網路資訊檢索
- 📁 **文件搜索** - 文檔查詢
- 💻 **代碼解釋器** - 執行 Python 代碼
- 🖱️ **計算機使用** - 操作計算機介面

---

## 📝 使用建議

### 最適合的場景
1. **編碼任務**
   - 代碼生成與調試
   - 代碼審查與重構
   - 技術文檔撰寫

2. **子代理系統**
   - 多 Agent 協作
   - 任務分解執行
   - 自動化工作流程

3. **計算機操作**
   - UI 自動化
   - 瀏覽器控制
   - 系統操作任務

### 與其他模型對比
- **vs GPT-4**: 更快、更便宜，但能力略低
- **vs GPT-5**: 成本極低（約 1/10），適合高頻調用
- **vs Claude**: 上下文窗口更大（40萬 vs 20萬）

---

## 💡 實際應用範例

### 1. SlideCue 中的應用場景

```javascript
// 生成演講建議逐字稿
const response = await openai.chat.completions.create({
  model: "gpt-5.4-mini",
  messages: [
    { role: "system", content: "你是演講助理..." },
    { role: "user", content: "根據投影片內容生成建議逐字稿" }
  ],
  max_tokens: 500,
  temperature: 0.7
});
```

### 2. 成本優化策略

**使用緩存**（節省 90% 輸入成本）：
```javascript
const response = await openai.chat.completions.create({
  model: "gpt-5.4-mini",
  messages: [
    { 
      role: "system", 
      content: "長系統提示...",
      // 標記為可緩存
      cache_control: { type: "ephemeral" }
    },
    { role: "user", content: "短用戶問題" }
  ]
});
```

---

## 🚨 限制與注意事項

### 知識截止
- 只知道到 **2025-08-31** 的資訊
- 之後的事件需要使用 Web 搜索工具

### 輸出限制
- 單次最多 128K tokens 輸出
- 超過需要分段請求

### 不支持的功能
- ❌ 圖像生成（使用 DALL-E）
- ❌ 語音輸入/輸出（使用 Whisper/TTS）
- ❌ 視頻處理

---

## 📚 相關資源

- [OpenAI API 文檔](https://developers.openai.com/docs)
- [Chat Completions API](https://developers.openai.com/docs/api-reference/chat)
- [Function Calling Guide](https://developers.openai.com/docs/guides/function-calling)
- [定價計算器](https://openai.com/pricing)

---

## 🔄 更新歷史

- **2026-05-29**: 初始文檔建立
- **2025-08-31**: GPT-5.4 mini 發布

---

## 💼 在 SlideCue 中的應用

### 當前使用情境
SlideCue 可以使用 GPT-5.4 mini 來：

1. **生成建議逐字稿**
   - 成本低廉，適合即時生成
   - 40萬 tokens 上下文足以處理完整簡報

2. **主題匹配分析**
   - 判斷轉錄內容與主題卡片的匹配度
   - 高頻調用場景，成本效益高

3. **風格分析**
   - 分析演講者的表達風格
   - 提供個性化建議

### 預估成本
```
假設單次演講：
- 輸入: 50K tokens (投影片 + 歷史轉錄)
- 輸出: 2K tokens (建議逐字稿)

成本 = (50K × $0.75 / 1M) + (2K × $4.50 / 1M)
     = $0.0375 + $0.009
     = $0.0465 (約 NT$1.5)

使用緩存後:
     = $0.00375 + $0.009
     = $0.01275 (約 NT$0.4)
```

---

**文檔維護**: 請定期檢查 OpenAI 官方文檔以獲取最新資訊。
