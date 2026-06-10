# 訪談稿生成與即時訪談輔助系統架構設計

> 目標：輸入 BRD 初稿後，系統自動分析需求內容，產生可編輯的「訪談單元」與各單元內的「提問重點 / 建議提問」。訪談時，系統依目前單元顯示提問重點與建議提問，並透過 `gpt-realtime-whisper` 即時收音，判斷哪些重點已被充分回答。訪談結束後，系統必須可以立即產出一份 BRD 文件與一份完整逐字稿；若訪談中沒有取得足夠資訊，BRD 對應段落應明確標示「待補」，不得由 AI 自行補猜。

---

## 一、目標流程

```text
BRD 初稿上傳
  ↓
原文解析與 Section 切分
  ↓
InterviewTheme 全文分析
  ↓
建立訪談單元、提問依據、BRD 對應章節、優先順序
  ↓
依每個訪談單元產生提問重點卡與建議提問
  ↓
編輯模式：使用者調整訪談單元、提問重點、建議提問、順序
  ↓
訪問模式：顯示目前單元的提問重點與建議提問
  ↓
Realtime Whisper 即時轉錄
  ↓
Answer Evaluation Engine 判斷提問重點是否已充分回答
  ↓
已回答且足以產出正式 BRD 的重點卡自動畫掉 / 標記完成
  ↓
訪談結束後依重點卡 evidence 與 transcript 產出 BRD 草稿
  ↓
使用者取得最終交付物：BRD 文件 + 訪談逐字稿
```

這個流程的核心不是「逐段 markdown 產生問題」，而是「從 BRD 初稿推導出訪談策略」。`Section` 只代表原始文件來源，`InterviewTheme` 才是使用者實際編輯與訪談時操作的主體。

---

## 二、核心概念重新定義

### 1. Section：原文來源單位

`Section` 保留目前功能，負責記錄 BRD 初稿切分後的原文段落。

用途：

- 保存來源文字與段落標題
- 提供 AI 追溯原文依據
- 支援 BRD 章節對應與 evidence trace

限制：

- 不再作為訪談流程的主要 UI 單位
- 不再逐 section 直接產生最終問題卡

### 2. InterviewTheme：訪談單元

`InterviewTheme` 是 BRD 初稿經 AI 全文分析後產出的訪談邏輯單元，對應 `BU_訪談問題稿與提問依據_BRD準備.md` 中「三、訪談問題稿」的每個大段。

範例：

- 0. 訪談開場與範圍確認
- 1. 現行作業流程
- 2. 使用者與角色
- 3. 客戶條件與排序依據
- 4. 服務建議內容
- 5. User Cases 補齊
- 6. 例外與阻擋條件
- 7. 資料來源與更新頻率
- 8. 系統串接與操作流程
- 9. 覆核、稽核與責任歸屬
- 10. 成功指標與驗收標準
- 11. BRD 必填資訊確認
- 12. 訪談結尾確認

每個訪談單元包含：

- 單元標題
- 提問依據
- 對應 BRD 章節
- 來源 Section
- 訪談優先順序
- 預估訪談時間
- 單元內的提問重點卡

### 3. QuestionCard：提問重點卡

`QuestionCard` 的語意要從「一張問題卡」調整為「一個需要被回答的 BRD 資訊缺口」。

卡片在 UI 上可以顯示：

- 提問重點：這張卡要補齊什麼資訊
- 建議提問：訪談者可以怎麼問
- 追問方向：回答不足時可以怎麼追
- 期待回答要素：什麼內容算回答完整
- BRD 對應章節：這張卡會餵入哪個 BRD 區塊
- 即時狀態：未問、聆聽中、部分充分、已充分、風險、略過、手動完成

訪談模式中被畫掉的對象應該是「提問重點卡」，而不是單純「一句建議問題」。因為 BU 可能沒有逐字回答某個建議提問，但只要該重點所需資訊已足夠產出正式 BRD，就應視為完成。

---

## 三、資料模型設計

### 1. Document

保留現有模型，新增或強化文件層級的訪談摘要欄位。

建議欄位：

```python
interview_objective: Text
interview_priority_order: JSON      # theme id / theme number array
interview_priority_reasoning: Text
interview_generation_version: String
```

### 2. InterviewTheme

目前 repo 已有 `backend/app/models/interview_theme.py`，可作為基礎，但需要補足排序、編輯與狀態需求。

建議模型：

```python
class InterviewTheme(Base):
    __tablename__ = "interview_themes"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)

    theme_number = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    rationale = Column(Text, nullable=False)
    brd_mapping = Column(ARRAY(String), nullable=False, default=list)
    priority = Column(Integer, nullable=False, default=99)
    estimated_minutes = Column(Integer, nullable=True)
    source_section_ids = Column(ARRAY(String), nullable=True)

    order_index = Column(Integer, nullable=False, default=0)
    is_required = Column(Boolean, nullable=False, default=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    user_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
```

### 3. QuestionCard

目前 `QuestionCard` 已有 `interview_theme_id`，但 `section_id` 仍是必填。新架構下要把 `interview_theme_id` 變成主要歸屬，`section_id` 只作為 optional source reference。

建議調整：

```python
class QuestionCard(Base):
    __tablename__ = "question_cards"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    interview_theme_id = Column(String, ForeignKey("interview_themes.id"), nullable=False, index=True)

    # optional source reference
    section_id = Column(String, ForeignKey("sections.id"), nullable=True, index=True)
    source_section_ids = Column(ARRAY(String), nullable=True)

    focus_text = Column(Text, nullable=False)       # 提問重點
    question_text = Column(Text, nullable=False)    # 建議提問
    suggested_followup = Column(Text, nullable=True)
    expected_answer_elements = Column(ARRAY(Text), nullable=True)
    brd_mapping = Column(ARRAY(String), nullable=True)

    importance = Column(String, nullable=False)     # must / should / optional
    coverage_rule = Column(JSON, nullable=False)
    estimated_seconds = Column(Integer, nullable=False, default=90)
    order_index = Column(Integer, nullable=False, default=0)

    status = Column(String, nullable=False, default="pending")
    confidence = Column(Numeric(4, 3), nullable=True, default=0)
    ui = Column(JSON, nullable=True)
    created_by = Column(String, nullable=False, default="ai")
```

若短期不想大改資料庫，可以先用現有欄位承載：

| 目標語意 | 短期欄位 |
|---|---|
| 提問重點 | `question_text` 或 `ui.focusText` |
| 建議提問 | `suggested_followup` 或 `ui.suggestedQuestions[]` |
| BRD 對應 | `ui.brdMapping` |
| Theme 歸屬 | `interview_theme_id` |

長期仍建議把 `focus_text` 與 `question_text` 拆開，否則「重點」與「問法」會混在一起，Realtime 評分也容易偏向逐字問句，而不是 BRD 資訊完整度。

### 4. InterviewSession

目前 session 使用 `current_section_id`。新架構應改為 theme 導向。

建議調整：

```python
current_theme_id = Column(String, ForeignKey("interview_themes.id"), nullable=True)
```

過渡期可保留 `current_section_id`，但 API 與前端應逐步改用：

```json
{
  "currentThemeId": "theme_xxx"
}
```

### 5. Utterance

轉錄內容應綁定目前訪談單元，而不是原始 section。

建議調整：

```python
theme_id = Column(String, ForeignKey("interview_themes.id"), nullable=True)
section_id = Column(String, ForeignKey("sections.id"), nullable=True)  # legacy/source
```

---

## 四、AI 生成 Pipeline

### 階段 0：文件解析

輸入 BRD 初稿，維持現有文件解析與 markdown section 切分。

輸出：

- `Document`
- `Section[]`

這階段不直接產生最終問題卡，只提供全文分析的來源材料。

### 階段 1：InterviewTheme 全文分析

輸入：

- document title
- full document text
- section list
- optional domain hint

輸出：

```json
{
  "interview_objective": "本次訪談的主要目標...",
  "themes": [
    {
      "theme_number": 0,
      "title": "訪談開場與範圍確認",
      "rationale": "此段用來先界定本次需求範圍...",
      "brd_mapping": ["需求背景", "需求範圍", "MVP 定義", "不做範圍"],
      "priority": 1,
      "estimated_minutes": 5,
      "source_section_ids": ["sec_xxx", "sec_yyy"]
    }
  ],
  "priority_order": [0, 3, 1, 4, 6],
  "priority_reasoning": "若訪談時間有限，建議優先確認範圍、排序規則、服務建議與例外條件..."
}
```

AI 任務：

- 找出 BRD 初稿中的缺口與不確定性
- 將缺口整理成訪談單元
- 為每個單元寫出提問依據
- 標註對應 BRD 章節
- 排出訪談優先順序
- 避免逐段照抄原文標題

### 階段 2：每個 Theme 產生提問重點卡

輸入：

- theme title
- theme rationale
- BRD mapping
- source sections text
- full document summary

輸出：

```json
{
  "theme_number": 3,
  "cards": [
    {
      "focus_text": "釐清服務優先級最重要的判斷因素",
      "question_text": "BU 認為服務優先級最重要的判斷因素有哪些？",
      "question_type": "clarification",
      "importance": "must",
      "expected_answer_elements": [
        "主要排序因子",
        "各因子的優先順序",
        "因子衝突時的決策原則",
        "是否有既有規則可依循"
      ],
      "suggested_followup": "若 KYC、資產級距與交易頻率互相衝突，排序應以哪個為主？",
      "brd_mapping": ["排序規則", "商業規則", "判斷邏輯"],
      "coverage_rule": {
        "semanticAnchors": ["服務優先級", "判斷因素", "排序因子"],
        "expectedKeywords": ["KYC", "資產", "交易頻率", "優先", "規則"],
        "mustMentionElements": [
          {
            "text": "說明至少三個主要排序因子",
            "required": true,
            "aliases": ["判斷因素", "評分因子", "排序條件"],
            "subpoints": []
          },
          {
            "text": "說明因子衝突時的優先原則",
            "required": true,
            "aliases": ["衝突時", "以哪個為主", "權重"],
            "subpoints": []
          }
        ],
        "thresholds": {
          "probablySufficient": 0.65,
          "sufficient": 0.8
        }
      }
    }
  ]
}
```

AI 任務：

- 每張卡代表一個 BRD 資訊缺口
- `focus_text` 用於評分與畫掉卡片
- `question_text` 用於訪談者現場參考
- `expected_answer_elements` 用於判斷回答是否足以產出正式 BRD
- `coverage_rule` 應比目前更偏向語意完整度，而不是單純 keyword matching

### 階段 3：品質檢查與去重

儲存前需要做基本 validation：

- 每個 theme 至少 3 張卡，核心 theme 可 6-10 張
- 每張卡必須有 `focus_text`
- 每張 must 卡必須有至少 2 個 expected answer elements
- 同一 theme 內問題不可高度重複
- `coverage_rule.thresholds.sufficient` 預設不得低於 0.75
- 建議提問不可要求完整帳號、身分證字號等敏感個資

---

## 五、後端架構

### 1. Worker：`document_analysis_worker.py`

目前 worker 是逐 section 呼叫 `openai_service.analyze_document_section()`。

新流程建議改為：

```text
analyze_document(document_id)
  ├─ load document + sections
  ├─ build full_document_context
  ├─ openai_service.generate_interview_themes(...)
  ├─ persist InterviewTheme[]
  ├─ for each theme:
  │    ├─ collect source section text
  │    ├─ openai_service.generate_theme_question_cards(...)
  │    └─ persist QuestionCard[] with interview_theme_id
  ├─ update document interview metadata
  └─ publish SSE events
```

建議新增事件：

```json
{ "type": "THEME_CREATED", "themeId": "theme_xxx", "themeNumber": 3 }
{ "type": "THEME_CARDS_CREATED", "themeId": "theme_xxx", "count": 8 }
{ "type": "INTERVIEW_PLAN_COMPLETE", "documentId": "doc_xxx", "themeCount": 13, "cardCount": 72 }
```

### 2. OpenAI Service

新增方法：

```python
generate_interview_themes(document, sections) -> dict
generate_theme_question_cards(document, theme, source_sections) -> dict
repair_interview_plan(plan, validation_errors) -> dict
```

保留 `analyze_document_section()` 作為 legacy fallback。

### 3. Theme Service

新增 `backend/app/services/interview_theme_service.py`：

職責：

- CRUD `InterviewTheme`
- 更新排序
- 更新提問依據
- 啟用 / 停用單元
- 查詢 theme + cards
- 回傳訪談模式需要的 active theme payload

### 4. Question Card Service

調整為支援 theme 操作：

- `get_question_cards_by_theme(theme_id)`
- `reorder_theme_cards(theme_id, card_ids)`
- `create_question_card(..., interview_theme_id=...)`
- `update_focus_text(card_id, focus_text)`

短期可保留 section-based API，但前端新頁面應優先使用 theme-based API。

### 5. Answer Evaluation Engine

目前回答評估接收 `section_id`，查詢該 section 內卡片。

新流程應改為：

```python
process_utterance(
    session_id,
    utterance_id,
    utterance_text,
    theme_id,
    speaker
)
```

評估範圍：

- 只評估目前 theme 中尚未完成的卡片
- 對 `focus_text`、`expected_answer_elements`、`coverage_rule` 評分
- 若回答足以支援 BRD 產出，狀態改為 `sufficient`
- 若回答部分涵蓋，狀態改為 `probably_sufficient`
- 保存 evidence transcript 與 matched elements

狀態語意：

| 狀態 | 語意 |
|---|---|
| `pending` | 尚未取得足夠資訊 |
| `listening` | 目前轉錄內容正在靠近此重點 |
| `probably_sufficient` | 大致回答，但 BRD 仍可能需要補細節 |
| `sufficient` | 足以產出正式 BRD 內容 |
| `at_risk` | 離開單元時 must 卡仍未完成 |
| `skipped` | 使用者略過 |
| `manually_checked` | 使用者手動標記完成 |
| `disabled` | 此卡不納入本次訪談 |

### 6. Realtime Whisper

Realtime Whisper 只負責「即時收音與轉錄」，不要讓它承擔判斷邏輯。

建議資料流：

```text
Browser mic
  → OpenAI Realtime WebRTC transcription
  → frontend receives transcript delta/completed
  → POST /interview-sessions/{id}/partial-transcript-match with themeId
  → POST /interview-sessions/{id}/utterances with themeId
  → AnswerEvaluationEngine
  → SSE CARD_STATE_UPDATED
  → frontend card crossed out
```

partial transcript 用於即時感；completed transcript 用於 durable evidence。

---

## 六、API 設計

### 1. Theme APIs

```http
GET /api/documents/{document_id}/interview-plan
```

回傳：

```json
{
  "documentId": "doc_xxx",
  "interviewObjective": "...",
  "priorityOrder": ["theme_0", "theme_3", "theme_1"],
  "priorityReasoning": "...",
  "themes": [
    {
      "id": "theme_0",
      "themeNumber": 0,
      "title": "訪談開場與範圍確認",
      "rationale": "...",
      "brdMapping": ["需求背景", "需求範圍"],
      "priority": 1,
      "estimatedMinutes": 5,
      "orderIndex": 0,
      "cards": []
    }
  ]
}
```

```http
PATCH /api/interview-themes/{theme_id}
PATCH /api/interview-themes/{theme_id}/cards/reorder
PATCH /api/documents/{document_id}/interview-themes/reorder
POST /api/interview-themes/{theme_id}/cards
```

### 2. Session APIs

```http
PATCH /api/interview-sessions/{session_id}/current-theme
```

Body：

```json
{
  "themeId": "theme_3"
}
```

```http
POST /api/interview-sessions/{session_id}/utterances
```

Body：

```json
{
  "themeId": "theme_3",
  "speaker": "interviewee",
  "transcript": "我們主要會看 KYC 風險屬性、近三個月交易頻率，以及資產級距...",
  "realtimeItemId": "item_xxx"
}
```

```http
POST /api/interview-sessions/{session_id}/partial-transcript-match
```

Body：

```json
{
  "themeId": "theme_3",
  "speaker": "interviewee",
  "transcript": "主要會看 KYC 風險屬性...",
  "realtimeItemId": "item_xxx"
}
```

---

## 七、前端架構

### 1. 編輯模式

目標：使用者可以編輯訪談單元與單元內的提問重點。

建議版面：

```text
┌─────────────────────────────────────────────────────────────┐
│ Header: 準備模式 / 分析成本 / 開始訪談                         │
├───────────────┬────────────────────────┬────────────────────┤
│ 訪談單元列表   │ 單元內容                 │ 提問重點卡           │
│               │                        │                    │
│ 0 開場        │ 標題                    │ [重點卡 1]          │
│ 1 現行流程     │ 提問依據                 │ [重點卡 2]          │
│ 2 使用者角色   │ 對應 BRD 章節            │ [重點卡 3]          │
│ 3 排序依據     │ 來源段落                 │                    │
│ ...           │ 優先順序 / 預估時間       │ 新增 / 排序 / 停用   │
└───────────────┴────────────────────────┴────────────────────┘
```

使用者可編輯：

- 單元名稱
- 提問依據
- 單元順序
- 單元是否納入本次訪談
- 提問重點
- 建議提問
- 追問方向
- 期待回答要素
- 重要度
- BRD 對應章節

不建議在編輯模式中仍以 slide/section 為主畫面，因為 BRD 訪談不是簡報逐頁講解，而是依需求缺口進行訪談。

### 2. 訪問模式

目標：讓訪談者專注在目前單元，而不是看到一堆原文段落。

建議版面：

```text
┌─────────────────────────────────────────────────────────────┐
│ Header: 訪問模式 / 錄音狀態 / 暫停 / 結束                       │
├───────────────┬────────────────────────┬────────────────────┤
│ 訪談單元導覽   │ 目前單元                 │ 建議提問             │
│               │                        │                    │
│ 0 開場 ✓      │ 3. 客戶條件與排序依據     │ 1. BU 認為...       │
│ 1 現行流程 ✓   │ 提問依據                 │ 2. KYC 屬性中...    │
│ 2 使用者角色   │ 此段為了釐清...          │ 3. 資產級距應...    │
│ 3 排序依據 ●   │                        │                    │
│ ...           │ 提問重點卡               │                    │
│               │ [ ] 排序因子             │                    │
│               │ [/] 因子衝突規則          │                    │
│               │ [x] 既有人工排序邏輯      │                    │
├───────────────┴────────────────────────┴────────────────────┤
│ 即時轉錄區：顯示最近轉錄、目前正在聽取內容                      │
└─────────────────────────────────────────────────────────────┘
```

右側「建議提問」顯示目前單元的可問句，卡片完成與否由中間「提問重點卡」呈現。

互動行為：

- 切換單元時更新 `currentThemeId`
- 離開單元時未完成的 must 卡標記 `at_risk`
- Realtime 收音只評估目前單元的卡片
- 卡片達 `sufficient` 時自動畫掉
- 使用者可以手動標記完成、略過、恢復

---

## 八、BRD 與逐字稿產出架構

訪談結束後，系統必須立即提供兩份交付物：

- BRD 文件：依訪談結果整理成正式 BRD 草稿，可直接給 BA / BU / IT 後續確認。
- 訪談逐字稿：依時間順序保存完整訪談 transcript，保留 speaker、時間、所屬訪談單元與來源 realtime item。

BRD generator 不應只讀完整 transcript，應優先讀結構化 evidence。完整逐字稿可作為補充查證來源，但不應讓 AI 在證據不足時自行推論正式需求。

建議輸入：

```json
{
  "themes": [
    {
      "title": "客戶條件與排序依據",
      "brdMapping": ["排序規則", "商業規則"],
      "cards": [
        {
          "focusText": "釐清服務優先級最重要的判斷因素",
          "status": "sufficient",
          "expectedAnswerElements": ["主要排序因子", "因子優先順序"],
          "evidenceTranscript": "我們主要看 KYC、資產級距、近三個月交易頻率..."
        }
      ]
    }
  ],
  "fullTranscript": "..."
}
```

BRD 生成策略：

- 依 `brdMapping` 分流到 BRD 章節
- `sufficient` 卡作為主要內容來源
- `probably_sufficient` 卡標註待確認
- `at_risk` must 卡列入 Open Issues
- `skipped` 或 `disabled` 不作為正式內容依據
- 若某個 BRD 必填章節沒有足夠 evidence，該章節仍要產生，但內容標示「待補」
- 待補項目必須說明缺少什麼資訊、來源是哪個訪談單元 / 提問重點
- 不得因為初稿或模型常識推測出訪談中沒有確認過的規則、欄位、流程或驗收標準

逐字稿生成策略：

- 依 `created_at` 或音訊時間排序所有 `Utterance`
- 每句保留 `speaker`、`themeId`、`themeTitle`、`startedAt`、`endedAt`、`transcript`
- 同一訪談單元內可分段整理，但不得改寫原文內容
- 支援從 BRD 段落回溯到對應逐字稿 evidence

建議輸出格式：

```text
InterviewSession
  ├── BRD 文件
  │     ├── Markdown / DOCX / PDF
  │     ├── 已確認需求
  │     ├── 待補資訊
  │     └── Open Issues
  └── 訪談逐字稿
        ├── Markdown / TXT / DOCX
        ├── 依時間排序
        └── 依訪談單元標註
```

建議 API：

```http
POST /api/interview-sessions/{session_id}/outputs/generate
```

回傳：

```json
{
  "sessionId": "session_xxx",
  "brdDocumentId": "brd_xxx",
  "transcriptDocumentId": "transcript_xxx",
  "status": "ready",
  "outputs": {
    "brd": {
      "markdownUrl": "/api/interview-sessions/session_xxx/outputs/brd.md",
      "docxUrl": "/api/interview-sessions/session_xxx/outputs/brd.docx",
      "pdfUrl": "/api/interview-sessions/session_xxx/outputs/brd.pdf"
    },
    "transcript": {
      "markdownUrl": "/api/interview-sessions/session_xxx/outputs/transcript.md",
      "txtUrl": "/api/interview-sessions/session_xxx/outputs/transcript.txt"
    }
  },
  "missingInfoCount": 8
}
```

訪談模式結束畫面應提供：

- 立即產生 BRD
- 下載 BRD
- 下載逐字稿
- 查看待補資訊清單
- 回到訪談補問未完成重點

---

## 九、實施順序

### Phase 1：資料模型與 AI Pipeline

1. 補 migration：`interview_themes`、`question_cards.interview_theme_id`、session `current_theme_id`
2. 新增 `InterviewThemeSchema`
3. 新增 `interview_theme_service.py`
4. 新增 `openai_service.generate_interview_themes()`
5. 新增 `openai_service.generate_theme_question_cards()`
6. 改造 `document_analysis_worker.py` 為 theme-first pipeline

驗收標準：

- 上傳 BRD 初稿後，DB 內產生 `InterviewTheme[]`
- 每個 theme 下有多張 question card
- 生成結構接近 `BU_訪談問題稿與提問依據_BRD準備.md` 的「三、訪談問題稿」

### Phase 2：編輯模式改版

1. 新增 `interviewPlanAPI`
2. 新增 theme list UI
3. 單元內容區顯示 / 編輯提問依據
4. 卡片區改成 theme cards
5. 支援 theme 與 card reorder

驗收標準：

- 使用者可編輯訪談單元
- 使用者可編輯單元內提問重點與建議提問
- UI 不再以 section/slide 作為主要操作單位

### Phase 3：訪問模式改版

1. session 改用 `currentThemeId`
2. 訪問模式顯示目前 theme 的提問依據、提問重點、建議提問
3. 切換 theme 時保存目前進度
4. 離開 theme 時標記未完成 must 卡為 `at_risk`

驗收標準：

- 訪談者可依訪談單元進行訪談
- 右側建議提問隨 theme 切換
- 中間提問重點卡可被畫掉或手動標記

### Phase 4：Realtime 評估改為 Theme-first

1. `partial-transcript-match` 改收 `themeId`
2. `utterances` 改收 `themeId`
3. `AnswerEvaluationEngine` 只評估目前 theme cards
4. 評估以 `focus_text + expected_answer_elements + coverage_rule` 為主
5. SSE 推送卡片狀態更新

驗收標準：

- Realtime Whisper 持續收音
- BU 回答足夠時，對應提問重點卡自動畫掉
- 卡片完成判斷不是依是否逐字問過建議提問，而是依回答是否足以產出 BRD

### Phase 5：BRD 與逐字稿生成整合

1. BRD generator 讀取 theme/card evidence
2. 依 `brdMapping` 分派內容
3. 未完成 must 卡產生 Open Issues
4. 資訊不足的 BRD 段落產生「待補」內容，而不是補猜
5. Transcript exporter 依 utterances 產生完整逐字稿
6. 訪談結束畫面提供「產生 BRD 與逐字稿」操作
7. 產出正式 BRD 草稿與完整逐字稿

驗收標準：

- 訪談結束後可以立即產出 BRD 草稿與逐字稿
- BRD 章節內容可追溯到對應 theme/card/transcript
- 不足資訊會列為待補或 Open Issues，而不是被 AI 補猜
- 即使訪談資料不足，BRD 文件仍會產出，缺口以「待補」標示
- 逐字稿保留完整訪談內容，並標註對應訪談單元

---

## 十、關鍵設計決策

### 1. 為什麼 theme 要成為主要單位？

BRD 訪談的邏輯不是文件段落順序，而是需求釐清順序。以 theme 為主才能支援：

- 訪談開場與範圍確認
- 核心規則先問
- 例外與法遵集中處理
- 時間不足時優先問關鍵單元
- 訪談後依 BRD 章節整理結論

### 2. 為什麼要拆「提問重點」與「建議提問」？

因為訪談現場的回答不一定照建議問句發生。系統真正要判斷的是：

> 這個 BRD 資訊缺口是否已被回答到足以寫入正式文件？

所以：

- `focus_text` 是評分與完成狀態的核心
- `question_text` 是訪談者現場參考
- `suggested_followup` 是不足時補問

### 3. Realtime Whisper 的責任邊界

Realtime Whisper 只做即時轉錄。判斷是否足夠應由後端 Answer Evaluation Engine 負責，這樣才能：

- 保存 durable evidence
- 使用一致的 coverage rule
- 支援手動修正
- 支援訪談後 BRD 生成
- 避免前端判斷邏輯分散

### 4. BRD 生成不能只靠全文 transcript

全文 transcript 太鬆散，容易讓 AI 補猜。應以 theme/card evidence 為主，full transcript 為輔，才能產出可追溯、可審核的 BRD。若 evidence 不足，系統仍要產出 BRD 文件，但對應章節必須標示「待補」，並列出需要補問的資訊。

### 5. 最終交付物必須包含 BRD 與逐字稿

訪談模式不是只用來追蹤卡片完成度。使用者結束訪談後，系統的最後產出必須是：

- 一份 BRD 文件：已確認內容寫入正式章節，未確認內容寫成待補。
- 一份訪談逐字稿：完整保留訪談內容，供後續稽核、查證與需求追溯。

這兩份文件應從同一份 session evidence 產生，確保 BRD 內容可以回溯到逐字稿，而逐字稿也能標註對應的訪談單元。

---

## 十一、目前程式碼對應改造點

| 現有位置 | 現況 | 目標 |
|---|---|---|
| `backend/app/models/interview_theme.py` | 已有基礎模型 | 補 order/is_enabled/user_notes，成為主模型 |
| `backend/app/models/question_card.py` | `interview_theme_id` optional，`section_id` required | 改為 theme required，section optional |
| `backend/app/workers/document_analysis_worker.py` | 逐 section 分析並產生卡片 | 全文產生 theme，再逐 theme 產生卡片 |
| `backend/app/services/openai_service.py` | section analysis prompt | 新增 theme generation 與 theme card generation |
| `backend/app/services/interview_service.py` | session current section | 改為 current theme |
| `backend/app/api/routes/interview_sessions.py` | utterance / partial match 傳 sectionId | 改傳 themeId |
| `frontend/src/routes/EditorPage.tsx` | 左側 slide、右側 card | 改為左側 theme、中間 rationale、右側 cards |
| `frontend/src/components/PresenterMode/PresenterLayout.tsx` | current slide + topic cards | 改為 current theme + focus cards + suggested questions |
| `frontend/src/hooks/useRealtimeTranscription.ts` | 轉錄來源 | 保留，輸出改帶 currentThemeId |

---

## 十二、最小可行版本

如果要最快做出符合期待的版本，建議 MVP 範圍如下：

1. 使用現有 `InterviewTheme` 模型，不先大改所有欄位
2. 新增 theme generation prompt
3. 讓 worker 產生 theme，並把 question cards 綁到 `interview_theme_id`
4. `section_id` 暫時填入 theme 的第一個 source section，避免 migration 太大
5. Editor 先改成 theme list + rationale + cards
6. Presenter 先以 themeId 過濾 cards，但保留部分 legacy section API
7. partial/completed transcript 評估時用 theme cards
8. 訪談結束後先輸出 Markdown 版 BRD 與逐字稿，DOCX / PDF 可作為下一步

這樣可以最早驗證你的核心體驗：

- BRD 初稿可以轉成訪談單元
- 使用者可以編輯單元與提問重點
- 訪問模式會顯示該單元的提問重點與建議提問
- Realtime Whisper 會根據 BU 回答把已足夠產出 BRD 的重點卡畫掉
- 訪談結束後可以立即拿到 BRD 文件與逐字稿；不足資訊會被標示為待補
