# GPT-5.5 模型使用指南

**文檔來源:** https://developers.openai.com/api/docs/models/gpt-5.5  
**更新日期:** 2026-05-29  
**知識截止:** 2025-12-01

---

## 📋 模型概述

GPT-5.5 是 OpenAI 於 2025 年 12 月發布的**新型智能類別模型**，專為編碼和專業工作設計，具備最高等級的推理能力。

### 模型版本

| 項目 | 值 |
|------|---|
| **主要版本** | `gpt-5.5` |
| **快照版本** | `gpt-5.5-2026-04-23` |
| **發布日期** | 2025-12-01 |
| **模型類型** | 文本生成、多模態理解 |

---

## ⚡ 核心特性

### 1. 推理能力
- **等級:** 最高 (Highest)
- **適用場景:** 複雜邏輯推理、專業工作、編碼任務
- **優勢:** 深度理解、精準判斷、複雜問題解決

### 2. 速度表現
- **速度評級:** 快速 (Fast)
- **實際表現:** 在保持高推理能力的同時，提供快速響應

### 3. 多模態支持
- **輸入:** 文本 + 圖像
- **輸出:** 文本

---

## 📊 技術規格

| 規格項目 | 數值 | 說明 |
|---------|------|------|
| **上下文窗口** | 1,050,000 tokens | 超大上下文，可處理長文檔、多輪對話 |
| **最大輸出** | 128,000 tokens | 可生成長篇內容 |
| **速度** | 快速 | 快速響應 |
| **推理能力** | 最高 | 最強邏輯推理能力 |

### 推理努力等級 (Reasoning Effort)

支持調整推理深度：
- `none` - 無額外推理
- `low` - 低推理努力
- `medium` - 中等推理（**預設**）
- `high` - 高推理努力
- `xhigh` - 超高推理努力

---

## 💰 定價信息

### 標準定價（每百萬 tokens）

| 類型 | 價格 | 說明 |
|------|------|------|
| **輸入** | $5.00 / M tokens | 標準輸入 tokens |
| **快取輸入** | $0.50 / M tokens | 已快取的輸入（節省 90%） |
| **輸出** | $30.00 / M tokens | 生成的輸出 tokens |

### 特殊定價規則

⚠️ **超長提示符加價:**
- 當輸入 tokens > 272K 時
- 按全會話的 **2倍輸入** 和 **1.5倍輸出** 計價

⚠️ **資料駐留端點:**
- 額外收取 **10% 費用**

### 成本估算（SlideCue 專案）

#### 建議稿語意判斷（30分鐘演講）

**假設:**
- 每次檢查：500 tokens 輸入 + 150 tokens 輸出
- 30分鐘約 100 次檢查

**計算:**
```
輸入: 100 × 500 = 50,000 tokens = 0.05M tokens
      0.05M × $5.00 = $0.25

輸出: 100 × 150 = 15,000 tokens = 0.015M tokens
      0.015M × $30.00 = $0.45

總計: $0.70 / 30分鐘
```

#### Topic Matching Engine（30分鐘演講）

**假設:**
- 每次判斷：800 tokens 輸入 + 200 tokens 輸出
- 30分鐘約 150 次判斷

**計算:**
```
輸入: 150 × 800 = 120,000 tokens = 0.12M tokens
      0.12M × $5.00 = $0.60

輸出: 150 × 200 = 30,000 tokens = 0.03M tokens
      0.03M × $30.00 = $0.90

總計: $1.50 / 30分鐘
```

**SlideCue 完整演講成本估算:**
```
建議稿判斷: $0.70
Topic Matching: $1.50
總計: ~$2.20 / 30分鐘演講
```

---

## 🔧 API 使用方式

### 基本調用

```python
from openai import OpenAI

client = OpenAI(api_key="your-api-key")

response = client.chat.completions.create(
    model="gpt-5.5",  # 或 "gpt-5.5-2026-04-23"
    messages=[
        {
            "role": "system",
            "content": "你是語意理解專家"
        },
        {
            "role": "user",
            "content": "判斷演講者是否已經講完這個主題..."
        }
    ]
)
```

### 結構化輸出（推薦用於 SlideCue）

```python
response = client.chat.completions.create(
    model="gpt-5.5",
    messages=[...],
    response_format={"type": "json_object"}
)

result = json.loads(response.choices[0].message.content)
```

### 調整推理深度

```python
response = client.chat.completions.create(
    model="gpt-5.5",
    messages=[...],
    reasoning_effort="high"  # 更深入的推理
)
```

### 使用快取（節省成本）

```python
# 將系統提示標記為可快取
response = client.chat.completions.create(
    model="gpt-5.5",
    messages=[
        {
            "role": "system",
            "content": "長系統提示...",
            "cache_control": {"type": "ephemeral"}  # 啟用快取
        },
        {
            "role": "user",
            "content": "用戶問題"
        }
    ]
)
```

---

## 🎯 支持的功能

### ✅ 支援的功能

| 功能 | 狀態 | 說明 |
|------|------|------|
| **串流 (Streaming)** | ✅ | 即時接收響應 |
| **函數呼叫 (Function Calling)** | ✅ | 支援工具調用 |
| **結構化輸出 (Structured Outputs)** | ✅ | JSON 格式輸出 |
| **視覺理解 (Vision)** | ✅ | 支援圖像輸入 |
| **Web 搜尋** | ✅ | 即時網路搜尋 |
| **程式碼解釋器** | ✅ | 執行程式碼 |
| **檔案搜尋** | ✅ | 搜尋上傳的檔案 |
| **影像生成** | ✅ | 生成圖片 |
| **計算機使用** | ✅ | 執行計算 |
| **MCP (Model Context Protocol)** | ✅ | 支援 MCP 協議 |

### ❌ 不支援的功能

| 功能 | 狀態 |
|------|------|
| **微調 (Fine-tuning)** | ❌ |

---

## 📡 支援的 API 端點

| 端點 | 用途 | SlideCue 使用 |
|------|------|--------------|
| `/v1/chat/completions` | 聊天補全 | ✅ 主要使用 |
| `/v1/responses` | 響應生成 | - |
| `/v1/realtime` | 即時語音 | ✅ 轉錄使用 |
| `/v1/batch` | 批次處理 | 可選優化 |
| `/v1/embeddings` | 向量嵌入 | - (使用專門的 embedding 模型) |
| `/v1/fine-tuning` | 微調 | ❌ 不支援 |

---

## 🚦 速率限制

根據 API 層級的限制：

| 層級 | RPM (每分鐘請求數) | TPM (每分鐘 tokens) |
|------|------------------|-------------------|
| Tier 1 | 500 | 200,000 |
| Tier 2 | 5,000 | 5,000,000 |
| Tier 3 | 10,000 | 10,000,000 |
| Tier 4 | 10,000 | 20,000,000 |
| **Tier 5** | **15,000** | **40,000,000** |

**SlideCue 建議:**
- 確保帳號至少達到 Tier 2
- 生產環境建議 Tier 3 或以上

---

## 🎯 SlideCue 專案整合

### 當前使用場景

#### 1. 語意判斷與 Script Plan 推進
**文件:** `backend/app/services/semantic_judge_service.py`, `backend/app/services/script_plan_service.py`

```python
class SemanticJudgeService:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.SEMANTIC_UNDERSTANDING_MODEL
```

**用途:**
- 判斷演講者是否語意覆蓋智慧題詞或卡片重點
- 支援不按稿念，語意理解為主
- 輔助 Script Plan cursor 推進與 topic-card completion 判斷

**推理等級建議:** `medium`（預設）或 `high`

#### 2. Topic Matching Engine
**文件:** `backend/app/services/semantic_judge_service.py`

```python
class SemanticJudgeService:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.SEMANTIC_UNDERSTANDING_MODEL  # gpt-5.5
```

**用途:**
- 判斷演講者的發言是否覆蓋主題卡片
- 深度語意理解
- 提供置信度和推理說明

**推理等級建議:** `medium`

---

## ⚙️ 環境配置

### .env 文件設定

```bash
# OpenAI API Key
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxx

# 語意理解模型 - 使用 GPT-5.5
SEMANTIC_UNDERSTANDING_MODEL=gpt-5.5

# 可選：使用快照版本（更穩定）
# SEMANTIC_UNDERSTANDING_MODEL=gpt-5.5-2026-04-23

# 其他模型
EMBEDDING_MODEL=text-embedding-3-large
REALTIME_MODEL=gpt-4o-realtime-preview-2024-12-17
REALTIME_TRANSCRIPTION_MODEL=gpt-4o-mini
```

### config.py 配置

```python
# backend/app/core/config.py

class Settings(BaseSettings):
    # ...
    
    SEMANTIC_UNDERSTANDING_MODEL: str = "gpt-5.5"
    
    # ...
```

---

## 🔄 從舊版 GPT 遷移

### GPT-4o → GPT-5.5

**優勢:**
- ✅ 更強的推理能力
- ✅ 更大的上下文窗口 (128K → 1.05M)
- ✅ 更快的速度
- ✅ 更準確的語意理解

**成本變化:**
```
GPT-4o:
  輸入: $2.50/M
  輸出: $10.00/M

GPT-5.5:
  輸入: $5.00/M  (↑ 2倍)
  輸出: $30.00/M (↑ 3倍)
```

**建議:**
- 生產環境：使用 GPT-5.5（更準確）
- 開發測試：可考慮 GPT-5.4-mini（更便宜）

### 遷移步驟

1. **更新環境變數**
```bash
# .env
SEMANTIC_UNDERSTANDING_MODEL=gpt-5.5
```

2. **重啟服務**
```bash
# 停止當前服務
# 重新啟動
uvicorn app.main:app --reload
```

3. **驗證**
- 檢查日誌確認使用 gpt-5.5
- 測試語意判斷功能
- 監控成本變化

---

## 📈 性能優化建議

### 1. 使用快取（節省 90% 輸入成本）

**適用場景:**
- 系統提示詞固定
- 判斷規則固定
- 上下文說明固定

**實現:**
```python
# 將固定的系統提示標記為可快取
messages = [
    {
        "role": "system",
        "content": "你是語意理解專家...",  # 長系統提示
        "cache_control": {"type": "ephemeral"}
    },
    {
        "role": "user",
        "content": dynamic_user_query  # 動態內容
    }
]
```

**成本節省:**
```
原成本: $5.00/M tokens (輸入)
快取後: $0.50/M tokens (輸入)
節省: 90%
```

### 2. 批次處理

對於非即時判斷，使用 Batch API：

```python
# 創建批次任務
batch = client.batches.create(
    input_file_id=file_id,
    endpoint="/v1/chat/completions",
    completion_window="24h"
)
```

**優勢:**
- 成本降低 50%
- 適合離線分析

### 3. 調整推理深度

根據任務複雜度選擇：

| 任務 | 推理等級 | 成本 |
|------|---------|------|
| 簡單關鍵字匹配 | `low` | 最低 |
| 語意相似度判斷 | `medium` | 適中 |
| 複雜邏輯推理 | `high` | 較高 |
| 深度分析 | `xhigh` | 最高 |

**SlideCue 建議:** `medium`（預設）

---

## ⚠️ 重要注意事項

### 1. Token 限制

- **輸入上限:** 1,050,000 tokens
- **輸出上限:** 128,000 tokens
- **超長輸入:** > 272K 時價格翻倍

### 2. 速率限制

注意 API 層級限制，避免：
- 過快的請求導致 429 錯誤
- 超過 TPM 限制

### 3. 成本控制

**監控重點:**
- 每次調用的 token 用量
- 快取命中率
- 月度總成本

**優化方向:**
- 優化提示詞長度
- 使用快取機制
- 合理設置推理等級

### 4. 錯誤處理

```python
try:
    response = client.chat.completions.create(...)
except openai.RateLimitError:
    # 速率限制，等待後重試
    time.sleep(60)
except openai.InvalidRequestError as e:
    # 請求參數錯誤
    logger.error(f"Invalid request: {e}")
except Exception as e:
    # 其他錯誤
    logger.error(f"API error: {e}")
```

---

## 🆚 模型比較

| 特性 | GPT-5.5 | GPT-5.4 | GPT-4o | GPT-4o-mini |
|------|---------|---------|---------|-------------|
| 推理能力 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| 速度 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 上下文 | 1.05M | - | 128K | 128K |
| 輸入價格 | $5.00 | $2.50 | $2.50 | $0.15 |
| 輸出價格 | $30.00 | - | $10.00 | $0.60 |
| **推薦場景** | **生產** | 平衡 | 開發 | 測試 |

---

## 📚 參考資源

- **官方文檔:** https://developers.openai.com/api/docs/models/gpt-5.5
- **API 參考:** https://developers.openai.com/api-reference
- **定價頁面:** https://openai.com/api/pricing
- **更新日誌:** https://openai.com/changelog

---

## ✅ 檢查清單

使用 GPT-5.5 前請確認：

- [ ] API Key 已設定
- [ ] 環境變數已更新為 `gpt-5.5`
- [ ] 帳號層級足夠（建議 Tier 2+）
- [ ] 已測試基本功能
- [ ] 已設置成本監控
- [ ] 已實現錯誤處理
- [ ] 考慮使用快取優化
- [ ] 了解定價規則

---

## 🔮 未來規劃

GPT-5.5 的長期使用建議：

1. **監控新版本**
   - 關注 `gpt-5.5-YYYY-MM-DD` 快照更新
   - 測試新功能

2. **成本優化**
   - 實施快取策略
   - 考慮批次處理
   - 監控用量趨勢

3. **功能擴展**
   - 利用多模態能力（圖像理解）
   - 探索工具調用功能
   - 整合 MCP 協議

---

**最後更新:** 2026-05-29  
**維護者:** SlideCue 開發團隊  
**狀態:** ✅ 生產就緒
