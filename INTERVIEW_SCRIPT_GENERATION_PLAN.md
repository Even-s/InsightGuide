# 訪談問題稿生成功能 — 調整建議

> 目標：系統接收 BRD 初稿後，自動生成如 `BU_訪談問題稿與提問依據_BRD準備.md` 的結構化訪談稿。

---

## 目前系統 vs 目標產出

| 面向 | 目前系統 | 目標（BU_訪談問題稿） |
|------|---------|---------------------|
| 結構 | 按 markdown 標題切 section → 每段生成 2-5 個扁平問題卡 | 有層級：訪談目標 → 主題單元(0-12) → 每單元含「提問依據」+「建議提問」 |
| 問題脈絡 | 只有 `questionText` + `suggestedFollowup` | 每個主題有「為什麼要問」(提問依據)，讓訪談者理解問的原因 |
| 訪談流程 | 無，只是一堆獨立問題卡 | 有明確開場(範圍確認) → 核心主題 → 結尾(未決事項) |
| 優先排序 | 只有 must/should 重要度 | 有「訪談時間有限時建議先問哪 5 大區塊」的全局排序 |
| BRD 對應 | 無 | 每個主題明確對應 BRD 章節（需求背景、As-Is流程、商業規則…） |
| 後續整理 | 無 | 有「訪談後應整理出的關鍵結論」+ 訪談紀錄模板 |
| 問題品質 | 通用提問（2-5題/段） | 深度問題（8-10題/主題），針對具體初稿內容設計 |

---

## 需要做的調整

### 1. 資料模型調整

**新增 `InterviewTheme`（訪談單元/主題）模型**，位於 Section 和 QuestionCard 之間：

```
Document
  └── InterviewTheme (0-12 個主題單元)
        ├── theme_number: int
        ├── title: str ("現行作業流程"、"客戶條件與排序依據"…)
        ├── rationale: text (提問依據 — 為什麼要問這個主題)
        ├── brd_mapping: str[] (對應 BRD 章節)
        ├── priority: int (訪談優先順序)
        └── QuestionCard[] (該主題下的問題集)
```

目前的 `Section` 保留為「原文段落」，`InterviewTheme` 是 AI 分析後歸納的「訪談邏輯單元」。

### 2. OpenAI Prompt 重構

目前 prompt 是逐段分析、逐段生成問題。需要改為**兩階段**：

**階段一：全文分析 → 生成訪談架構**
- 輸入：整份 BRD 初稿全文
- 輸出：訪談目標 + 主題單元列表 + 各主題的提問依據 + BRD 對應 + 優先排序

**階段二：逐主題生成問題集**
- 輸入：單一主題 + 對應的原文片段 + 提問依據
- 輸出：該主題下的具體問題（含 coverage_rule、expected_answer_elements 等）

### 3. 新增的 OpenAI 輸出結構

階段一產出 JSON：
```json
{
  "interview_objective": "本次訪談的主要目標…",
  "themes": [
    {
      "number": 0,
      "title": "訪談開場與範圍確認",
      "rationale": "初版只定義需求方向…尚未明確第一階段範圍",
      "brd_sections": ["需求背景", "需求範圍", "MVP 定義"],
      "priority": 3,
      "source_sections": ["sec_xxx", "sec_yyy"]
    }
  ],
  "priority_order": [1, 3, 5, 6, 7],
  "priority_reasoning": "若訪談時間有限，建議優先..."
}
```

階段二產出 JSON（逐主題）：
```json
{
  "theme_number": 1,
  "questions": [
    {
      "question_text": "現在營業員如何盤點客戶狀態？請描述從查詢客戶資料到產出服務建議的完整流程。",
      "question_type": "clarification",
      "importance": "must",
      "expected_answer_elements": ["現行步驟", "使用工具", "耗時", "判斷依據"],
      "suggested_followup": "這些資料目前分散在哪些系統或報表？",
      "coverage_rule": {
        "semantic_anchors": ["盤點流程", "客戶資料", "服務建議"],
        "expected_keywords": ["系統", "報表", "判斷", "耗時"],
        "must_mention_elements": [
          {"text": "描述完整流程步驟", "required": true, "aliases": ["作業流程", "操作步驟"], "subpoints": []}
        ],
        "thresholds": {"probably_sufficient": 0.65, "sufficient": 0.80}
      }
    }
  ]
}
```

### 4. 前端 EditorPage 調整

目前左側是「段落列表」(Slides)，右側是問題卡。需要改為：

- 左側：**訪談主題列表**（含優先排序標記）
- 中間：該主題的**提問依據**（讓訪談者了解為何要問）
- 右側：該主題下的**問題卡集合**

### 5. 新增「訪談流程」概覽

增加一個全局視圖，顯示：
- 訪談目標摘要
- 主題順序（可拖拉調整）
- 每個主題的時間預估
- 優先標記（時間不足時先問哪些）

### 6. 新增 BRD 對應功能

每個主題/問題標註它會餵入 BRD 的哪個章節，方便訪談後自動彙整成 BRD 草稿。

---

## 建議實施順序

1. **先改 prompt + 資料模型** — 讓 AI 能產出有結構的訪談稿（最高價值）
2. **前端顯示調整** — 左側改為主題列表、中間顯示提問依據
3. **訪談流程排序** — 全局排序 + 優先標記
4. **BRD 對應** — 問題到 BRD 章節的 mapping

---

## 參考文件

- 目標產出範例：`./BU_訪談問題稿與提問依據_BRD準備.md`
- 目前分析 prompt：`backend/app/services/openai_service.py` (lines 498-568)
- 目前分析 worker：`backend/app/workers/document_analysis_worker.py`
- 目前資料模型：`backend/app/models/section.py`, `backend/app/models/question_card.py`
