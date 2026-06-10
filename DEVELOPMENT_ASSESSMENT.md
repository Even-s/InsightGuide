# InsightGuide 開發過程評估報告

**評估日期**: 2026-06-10  
**評估範圍**: 完整專案代碼庫與開發歷史  
**評估方法**: 深度代碼審查、Git 歷史分析、架構一致性檢查

---

## 📊 執行摘要

### 開發狀態總覽

| 項目 | 狀態 | 完成度 | 說明 |
|------|------|--------|------|
| **品牌更名** | ✅ 完成 | 100% | 所有 SlideCue 引用已清除 |
| **資料模型** | 🟡 部分完成 | 60% | 核心模型已建立但與架構文件不一致 |
| **API 路由** | 🟡 部分完成 | 50% | 仍保留舊 SlideCue API 結構 |
| **前端組件** | 🟡 部分完成 | 40% | 大部分組件仍然是 SlideCue 風格 |
| **AI 服務** | ❌ 未完成 | 10% | 仍然使用 SlideCue 的簡報分析邏輯 |
| **答案評估引擎** | ❌ 未實作 | 0% | 核心功能完全缺失 |
| **BRD 文件生成** | ❌ 未實作 | 0% | README 中提及但未實作 |

**總體完成度**: **35%** (品牌更名完成，但核心業務邏輯尚未改造)

---

## 🔍 深度分析

### 1. 專案歷史與現狀

#### Git 提交歷史
```bash
# 整個專案只有一個提交
commit 0204cff (2026-06-02)
feat: Implement Milestone 7 - Session Report with comprehensive analytics
Author: SlideCue Dev <dev@slidecue.local>

# 這個提交是從 SlideCue 專案複製過來的完整代碼庫
```

**發現**:
- ❌ InsightGuide 專案是直接從 SlideCue 複製而來
- ❌ 沒有後續的開發提交記錄
- ❌ 所有 "unstaged changes" 都在 `../SlideCue/` 目錄下，不是在 InsightGuide 目錄

#### 當前工作目錄結構
```
/Users/cfh00914977/Project/
├── InsightGuide/          # 複製的乾淨代碼庫（只有品牌更名）
│   ├── backend/           # Python 後端
│   ├── frontend/          # React 前端
│   └── docs/              # 文檔（已清理 SlideCue 開發記錄）
└── SlideCue/              # 原始專案（有未提交的修改）
```

---

### 2. 資料模型分析

#### 已建立的模型（backend/app/models/）

✅ **已重命名的模型**:
```python
# 正確的 InsightGuide 模型
Document          # ✓ 取代 Deck
Section           # ✓ 取代 Slide  
QuestionCard      # ✓ 取代 TopicCard
InterviewSession  # ✓ 取代 PresentationSession
PrepSession       # ✓ 新增的準備階段模型
```

❌ **仍然保留的 SlideCue 模型**:
```python
# backend/app/models/__init__.py (line 11)
from app.models.presentation_session import PresentationSession

# backend/app/models/presentation_session.py
class PresentationSession(Base):
    """PresentationSession model - represents a presentation session."""
    __tablename__ = "presentation_sessions"
```

**問題**: 
- 同時存在 `InterviewSession` 和 `PresentationSession` 兩個模型
- API 路由和前端仍在使用 `PresentationSession`
- 造成架構混亂和概念不一致

---

### 3. API 路由分析

#### 當前 API 端點（backend/app/api/routes/）

| 檔案名 | 狀態 | 說明 |
|--------|------|------|
| `documents.py` | ✅ 正確 | 新的 InsightGuide API |
| `sections.py` | ✅ 正確 | 新的 InsightGuide API |
| `question_cards.py` | ✅ 正確 | 新的 InsightGuide API |
| `interview_sessions.py` | ✅ 正確 | 新的 InsightGuide API |
| `prep_sessions.py` | ✅ 正確 | 新的 InsightGuide API |
| `events.py` | ❌ 混亂 | 仍使用 `PresentationSession` |
| `session_reports.py` | ❌ 混亂 | 註釋和邏輯仍是簡報概念 |
| `realtime.py` | ⚠️ 部分 | 已更新但功能未改造 |

#### API 註冊（backend/app/main.py）

```python
# Line 50-70: API 路由註冊
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(sections.router, prefix="/api/sections", tags=["sections"])
app.include_router(question_cards.router, prefix="/api/question-cards", tags=["question-cards"])
app.include_router(interview_sessions.router, prefix="/api/interview-sessions", tags=["interview-sessions"])
app.include_router(prep_sessions.router, prefix="/api/prep-sessions", tags=["prep-sessions"])
app.include_router(events.router, prefix="/api/events", tags=["events"])
app.include_router(realtime.router, prefix="/api/realtime", tags=["realtime"])
app.include_router(session_reports.router, prefix="/api/interview-sessions", tags=["session-reports"])
```

**問題**:
- ✅ API 路徑已正確更新為 InsightGuide 術語
- ❌ 但內部實作仍然使用 SlideCue 的業務邏輯
- ❌ `events.py` 內部查詢 `PresentationSession` 表，應該查詢 `InterviewSession`

---

### 4. Service 層分析

#### 服務檔案清單（backend/app/services/）

**22 個服務檔案**，但大部分仍是 SlideCue 邏輯：

| 服務 | 狀態 | 問題 |
|------|------|------|
| `document_service.py` | ✅ 新建 | 已正確實作 |
| `section_service.py` | ✅ 新建 | 已正確實作 |
| `question_card_service.py` | ✅ 新建 | 已正確實作 |
| `interview_service.py` | ✅ 新建 | 已正確實作 |
| `prep_session_service.py` | ✅ 新建 | 已正確實作 |
| **舊 SlideCue 服務** | ❌ 殘留 | 以下仍然存在 |
| `deck_service.py` | ❌ 殘留 | 應該刪除或整合 |
| `slide_service.py` | ❌ 殘留 | 應該刪除或整合 |
| `topic_card_service.py` | ❌ 殘留 | 已被 question_card_service 取代 |
| `presentation_service.py` | ❌ 殘留 | 已被 interview_service 取代 |
| `ai_card_generator.py` | ⚠️ 問題 | 仍生成「topic card」和「slide context」 |
| `openai_service.py` | ⚠️ 問題 | Line 132: 系統提示詞已更新但分析邏輯未改 |
| `topic_matching_engine.py` | ❌ 錯誤 | 應改為「answer_evaluation_engine」 |
| `semantic_judge_service.py` | ⚠️ 問題 | 評估邏輯仍是「主題匹配」而非「答案充分度」 |
| `scoring_service.py` | ⚠️ 問題 | 計分邏輯基於簡報主題，而非需求回答 |

**核心問題**: 
```python
# backend/app/services/ai_card_generator.py (line 7)
"""AI service for generating topic card fields from title and script."""
# ❌ 仍然是「topic card」概念，應該是「question card」

# backend/app/services/topic_matching_engine.py
# ❌ 整個服務都是錯的！應該是 answer_evaluation_engine.py
# 邏輯是「匹配演講內容到投影片主題」
# 應該是「評估訪談回答的充分度」
```

---

### 5. 前端組件分析

#### 前端檔案統計
- **總計 73 個 TypeScript/TSX 檔案**
- **29 個 React 組件**

#### 關鍵組件狀態

| 組件路徑 | 狀態 | 說明 |
|----------|------|------|
| `routes/DocumentUploadPage.tsx` | ✅ 正確 | 新的 InsightGuide 上傳頁面 |
| `routes/InterviewPage.tsx` | ✅ 正確 | 新的訪談頁面架構 |
| `components/InterviewMode/` | ⚠️ 缺失 | 目錄存在但可能未實作完整 |
| `routes/EditorPage.tsx` | ❌ 殘留 | 仍是 SlideCue 的簡報編輯器 |
| `routes/PresenterPage.tsx` | ❌ 殘留 | 仍是 SlideCue 的演講者模式 |
| `components/EditorMode/SlidePreview.tsx` | ❌ 錯誤 | 應該顯示「文件章節」而非「投影片」 |
| `components/PresenterMode/` | ❌ 錯誤 | 整個目錄概念錯誤，應該是 InterviewMode |
| `stores/deckStore.ts` | ❌ 殘留 | 應改為 documentStore |
| `stores/presentationStore.ts` | ❌ 殘留 | 應改為 interviewStore |

**問題範例**:
```typescript
// frontend/src/routes/EditorPage.tsx
// ❌ 仍然載入 deck 和 slides
const { currentDeck, setCurrentDeck, loading, error } = useDeckStore()

// frontend/src/components/EditorMode/SlidePreview.tsx
// ❌ 顯示投影片預覽圖
<img src={slide.imageUrl} alt={`Slide ${slide.slideNumber}`} />

// ✓ 應該顯示需求文件章節
<div className="section-content">{section.extractedText}</div>
```

---

### 6. AI 服務邏輯分析

#### OpenAI 服務配置

```python
# backend/app/services/openai_service.py (Line 132)
system_prompt = "你是 InsightGuide 的需求文件分析專家"
# ✅ 系統提示詞已更新

# 但實際分析邏輯呢？
```

**深入檢查**:
```python
# backend/app/services/openai_service.py
def analyze_slide_with_gpt55(self, slide_text: str, ...) -> dict:
    """Analyze slide content with GPT-5.5."""
    # ❌ 函數名稱仍是 analyze_slide
    # ❌ 參數名稱仍是 slide_text
    # ❌ 應該改為 analyze_section 和 section_text
```

```python
# backend/app/services/ai_card_generator.py
def generate_card_metadata(
    self,
    title: str,
    suggested_script: str,
    slide_context: str = ""  # ❌ slide_context 應改為 section_context
) -> Dict[str, Any]:
    """Generate topic card metadata"""  # ❌ topic card 應改為 question card
```

**核心問題**:
- 系統提示詞改了，但分析邏輯沒改
- 仍在分析「簡報投影片」而非「需求文件章節」
- 仍在生成「演講主題卡」而非「訪談問題卡」

---

### 7. Answer Evaluation Engine（答案評估引擎）

#### 架構文件定義
```markdown
docs/architecture/InsightGuide_開發架構書.md

# 4.5 Answer Evaluation Engine（回答評估引擎）
目標：判斷訪談者的回答是否充分、完整，能否用於撰寫 BRD 文件。
```

#### 實際實作狀態
```bash
$ find backend/app/services -name "*answer*" -o -name "*evaluation*"
# (沒有結果)

$ grep -r "Answer.*Evaluation\|answer.*evaluation" backend/app/services/
# (沒有結果)
```

**結論**: ❌ **完全未實作**

**現有的替代品**:
```python
# backend/app/services/topic_matching_engine.py
class TopicMatchingEngine:
    """
    Topic Matching Engine - 判斷演講內容是否覆蓋投影片主題
    """
    # ❌ 這是 SlideCue 的主題匹配引擎
    # ❌ 邏輯完全不符合 InsightGuide 的需求評估需求
```

**應該是什麼**:
```python
# backend/app/services/answer_evaluation_engine.py (不存在)
class AnswerEvaluationEngine:
    """
    Answer Evaluation Engine - 判斷訪談回答是否充分
    
    評估維度:
    1. 回答完整性 (Completeness): 是否涵蓋所有預期要素
    2. 回答深度 (Depth): 是否提供足夠細節
    3. 可用性 (Usability): 是否能直接用於撰寫 BRD
    """
```

---

### 8. BRD 文件生成功能

#### README.md 宣稱
```markdown
### 訪談報告
- **BRD 文件草稿生成**：根據訪談內容自動生成 BRD 文件初稿，
  包含需求描述、功能清單、使用者故事等。
```

#### 實際實作
```bash
$ find backend/app -name "*brd*" -o -name "*requirements_doc*"
# (沒有結果)

$ grep -r "BRD\|Business.*Requirements\|需求文件生成" backend/app/
# (沒有結果)
```

**結論**: ❌ **完全未實作，README 中的功能宣稱是虛假的**

---

### 9. 資料庫 Migrations

#### 當前 Migrations
```bash
backend/app/db/migrations/versions/
├── 0edc97eda1b4_initial_schema.py
├── 78e7cabb32a4_make_prep_session_deck_id_unique.py  # ❌ deck_id？
├── 9a7f2b4d1c3e_add_ai_usage_events.py
├── b6d8f9a2c4e1_add_deck_ai_usage_events.py          # ❌ deck？
├── e3ab8962e5b9_add_prep_sessions_table.py
└── f4c2a1b8d9e0_add_presentation_pause_accounting.py # ❌ presentation？
```

**問題**:
- 部分 migration 檔案名稱仍然使用 `deck` 和 `presentation`
- 表結構可能同時存在舊表和新表
- 需要清理和重新規劃資料庫結構

---

### 10. 文檔與實作不一致

#### 架構文檔宣稱
```markdown
docs/architecture/InsightGuide_開發架構書.md

# 4.2 核心組件
- Document Service: 需求文件管理
- Section Service: 章節處理
- QuestionCard Service: 問題卡片管理
- InterviewSession Service: 訪談會話管理
- AnswerEvaluation Engine: 回答評估引擎 ⭐核心
```

#### 實際代碼庫
```python
# backend/app/services/
✓ document_service.py        # 存在
✓ section_service.py          # 存在
✓ question_card_service.py    # 存在
✓ interview_service.py        # 存在（不是 interview_session_service）
✗ answer_evaluation_engine.py # 不存在！！！

# 但同時存在不應該存在的:
✗ deck_service.py             # SlideCue 殘留
✗ slide_service.py            # SlideCue 殘留
✗ topic_card_service.py       # SlideCue 殘留
✗ presentation_service.py     # SlideCue 殘留
✗ topic_matching_engine.py   # SlideCue 殘留
```

---

## 🎯 核心問題總結

### 問題 1: 「偽重構」- 換湯不換藥

**表象**:
- ✅ 檔案名稱已重命名（Document, Section, QuestionCard, InterviewSession）
- ✅ API 端點路徑已更新（/api/documents, /api/interview-sessions）
- ✅ 資料庫表名已更新（documents, sections, question_cards）
- ✅ 前端頁面路由已更新（/documents/:id/editor, /documents/:id/interview）

**實質**:
- ❌ 業務邏輯未改變：仍在分析「簡報投影片」而非「需求文件」
- ❌ AI 服務未改變：仍在生成「演講主題卡」而非「訪談問題卡」
- ❌ 評估引擎未改變：仍在做「主題匹配」而非「答案充分度評估」
- ❌ 核心功能未實作：Answer Evaluation Engine、BRD 生成完全缺失

**比喻**: 就像把一輛「Ferrari（SlideCue 簡報助手）」的車殼換成「Tesla（InsightGuide 訪談助手）」的外觀，但引擎、傳動系統、控制邏輯全部沒變。

---

### 問題 2: 雙重人格 - 新舊系統並存

**現象**:
```python
# 資料模型同時存在
InterviewSession       # 新的訪談 session
PresentationSession    # 舊的簡報 session

# API 路由混亂
/api/interview-sessions/{id}       # 新 API
但內部查詢 PresentationSession 表  # 舊邏輯

# 前端組件目錄
components/InterviewMode/     # 新目錄（可能未完成）
components/PresenterMode/     # 舊目錄（仍在使用）
```

**後果**:
- 概念混亂：開發者不知道該用新的還是舊的
- 資料不一致：可能在錯誤的表中讀寫資料
- 維護困難：bug 修復需要同時考慮兩套系統

---

### 問題 3: 文檔作假 - 宣稱功能未實作

**README.md 宣稱**:
```markdown
### 訪談報告
- **BRD 文件草稿生成**：根據訪談內容自動生成 BRD 文件初稿
```

**實際情況**:
```bash
$ grep -r "BRD\|BusinessRequirements" backend/
# (沒有任何結果)
```

**其他虛假宣稱**:
- ❌ "Answer Evaluation Engine（回答評估引擎）" - 完全未實作
- ❌ "判斷問題回答是否足夠撰寫 BRD 文件" - 仍在做簡報主題匹配
- ⚠️ "GPT-5.5 需求文件分析" - 提示詞改了但邏輯沒變

---

### 問題 4: 核心邏輯錯誤 - Topic Matching ≠ Answer Evaluation

**SlideCue 的邏輯**:
```
演講者說話 → 語音轉文字 → 提取關鍵字和語意 
→ 匹配到投影片主題 → 判斷「這張投影片的主題是否已講過」
```

**InsightGuide 應該的邏輯**:
```
訪談者回答 → 語音轉文字 → 分析回答內容 
→ 比對問題要點 → 判斷「這個問題的回答是否充分、可用於撰寫 BRD」
```

**當前實作**:
```python
# backend/app/services/topic_matching_engine.py
def calculate_matching_score(utterance, topic_card):
    # 計算「utterance 匹配 topic 的分數」
    # ❌ 這是在判斷「是否談到這個主題」
    # ✓ 應該判斷「回答是否充分、是否可撰寫需求文件」
```

**差異本質**:
- SlideCue: **存在性檢測** (是否提到？) → 二元判斷（有/沒有）
- InsightGuide: **充分性評估** (回答得如何？) → 多維度評分（完整性、深度、可用性）

---

## 📋 待辦事項清單

### Phase 1: 清理遺留代碼 (優先級: P0)

**目標**: 移除所有 SlideCue 殘留，避免概念混亂

#### 1.1 資料模型清理
```bash
[ ] 刪除 PresentationSession 模型（已被 InterviewSession 取代）
[ ] 刪除 PresentationCardState（已被 InterviewCardState 取代）
[ ] 移除 models/__init__.py 中的 PresentationSession import
[ ] 檢查並修正所有引用 PresentationSession 的代碼
```

#### 1.2 Service 層清理
```bash
[ ] 刪除 deck_service.py（已被 document_service 取代）
[ ] 刪除 slide_service.py（已被 section_service 取代）
[ ] 刪除 topic_card_service.py（已被 question_card_service 取代）
[ ] 刪除 presentation_service.py（已被 interview_service 取代）
[ ] 重命名 topic_matching_engine.py → answer_evaluation_engine.py
[ ] 刪除或整合 transcription_service.py
```

#### 1.3 API 路由清理
```bash
[ ] events.py: 改用 InterviewSession 而非 PresentationSession
[ ] session_reports.py: 移除簡報概念的註釋和邏輯
[ ] 檢查所有 API 確保不再查詢舊表
```

#### 1.4 前端清理
```bash
[ ] 刪除 components/PresenterMode/ 目錄
[ ] 刪除 routes/PresenterPage.tsx
[ ] 刪除 stores/deckStore.ts
[ ] 刪除 stores/presentationStore.ts
[ ] 刪除 api/decks.ts
[ ] 刪除 api/presentation.ts
[ ] 移除所有對 "deck", "slide", "topic", "presentation" 的引用
```

---

### Phase 2: 重構核心業務邏輯 (優先級: P0)

**目標**: 將 SlideCue 的簡報分析邏輯改為 InsightGuide 的需求訪談邏輯

#### 2.1 AI 服務改造
```python
# backend/app/services/openai_service.py

[ ] analyze_slide_with_gpt55() → analyze_section_with_gpt55()
    - 輸入: section_text（需求文件章節內容）
    - 輸出: 章節摘要 + 關鍵需求點 + 建議問題

[ ] 新增 generate_questions_for_section()
    - 輸入: section 內容 + ai_summary
    - 輸出: List[QuestionCard]
    - 邏輯: 基於需求內容生成訪談問題，而非基於簡報主題
```

#### 2.2 Question Card 生成改造
```python
# backend/app/services/ai_card_generator.py

[ ] generate_card_metadata() 改為 generate_question_metadata()
    - 移除 slide_context 參數
    - 改為 section_context: 需求章節背景
    - 改為 expected_answer_points: 預期回答要點

[ ] 改變生成邏輯:
    - 舊: "這個主題要講什麼？" + "關鍵字" + "重要事實"
    - 新: "這個需求要問什麼？" + "預期回答要素" + "深度要求"
```

#### 2.3 重寫 Answer Evaluation Engine
```python
# backend/app/services/answer_evaluation_engine.py (新建)

[ ] 建立 AnswerEvaluationEngine 類別

[ ] 實作 evaluate_answer_completeness()
    """
    評估回答完整性
    - 是否涵蓋所有 expected_answer_elements？
    - 是否提及所有 must_mention_facts？
    - 回答深度是否足夠？
    """

[ ] 實作 calculate_sufficiency_score()
    """
    計算回答充分度分數 (0.0 - 1.0)
    - completeness: 要素完整性 (40%)
    - depth: 回答深度 (30%)
    - clarity: 表達清晰度 (15%)
    - usability: BRD 可用性 (15%)
    """

[ ] 實作 determine_question_status()
    """
    判斷問題狀態
    - insufficient: < 0.4 - 需要追問
    - partially_sufficient: 0.4-0.7 - 建議補充
    - sufficient: > 0.7 - 可以進入 BRD
    """

[ ] 實作 generate_followup_suggestions()
    """
    根據缺失要素生成追問建議
    - 哪些要素未提及？
    - 哪些回答不夠深入？
    - 建議的追問問題是什麼？
    """
```

---

### Phase 3: 實作缺失的核心功能 (優先級: P1)

#### 3.1 BRD 文件生成服務
```python
# backend/app/services/brd_generator_service.py (新建)

[ ] 建立 BRDGeneratorService 類別

[ ] 實作 generate_brd_draft()
    """
    根據訪談內容生成 BRD 草稿
    
    輸入:
    - interview_session: 訪談記錄
    - question_cards: 問題卡片 + 回答充分度
    - utterances: 完整逐字稿
    
    輸出:
    - BRD Markdown 文件
    
    結構:
    1. 需求概述
    2. 功能需求清單
    3. 非功能需求
    4. 使用者故事
    5. 驗收標準
    6. 附錄：訪談逐字稿摘要
    """

[ ] 實作 extract_requirements_from_answers()
    """
    從回答中提取結構化需求
    - 功能需求
    - 數據需求
    - 介面需求
    - 性能需求
    """

[ ] 實作 generate_user_stories()
    """
    從需求和回答生成使用者故事
    格式: "作為[角色]，我想要[功能]，以便[價值]"
    """
```

#### 3.2 BRD API 端點
```python
# backend/app/api/routes/brd_generation.py (新建)

[ ] POST /api/interview-sessions/{session_id}/generate-brd
    - 觸發 BRD 生成
    - 返回 job_id 供輪詢

[ ] GET /api/interview-sessions/{session_id}/brd-status
    - 查詢 BRD 生成狀態

[ ] GET /api/interview-sessions/{session_id}/brd-draft
    - 下載生成的 BRD Markdown
    - 支援匯出為 PDF
```

---

### Phase 4: 資料庫重構 (優先級: P1)

#### 4.1 清理舊表
```python
# backend/app/db/migrations/versions/xxx_cleanup_slidecue_tables.py

[ ] 建立 migration 刪除舊表:
    - DROP TABLE IF EXISTS presentation_sessions;
    - DROP TABLE IF EXISTS presentation_card_states;
    - DROP TABLE IF EXISTS decks;  （如果還存在）
    - DROP TABLE IF EXISTS slides; （如果還存在）
    - DROP TABLE IF EXISTS topic_cards; （如果還存在）
```

#### 4.2 新增 BRD 相關表
```python
# backend/app/db/migrations/versions/xxx_add_brd_generation.py

[ ] 建立 brd_drafts 表:
    - id: Primary key
    - interview_session_id: Foreign key
    - status: generating / completed / failed
    - markdown_content: Text
    - pdf_url: S3 URL
    - generated_at: Timestamp

[ ] 建立 requirements 表（從 BRD 提取的結構化需求）:
    - id: Primary key
    - brd_draft_id: Foreign key
    - requirement_type: functional / non-functional / data / interface
    - title: String
    - description: Text
    - priority: must / should / optional
    - source_question_card_id: Foreign key（來源問題）
```

---

### Phase 5: 前端重構 (優先級: P2)

#### 5.1 編輯器模式改造
```typescript
// frontend/src/routes/EditorPage.tsx

[ ] 移除投影片預覽功能
[ ] 改為顯示需求文件章節列表
[ ] 章節卡片顯示:
    - 章節標題
    - 章節摘要
    - 關聯的 Question Cards 數量
    - AI 分析狀態

// frontend/src/components/EditorMode/SectionView.tsx (新建)
[ ] 建立章節視圖組件
    - 顯示章節內容
    - 顯示 AI 摘要
    - 顯示生成的問題列表
```

#### 5.2 訪談模式改造
```typescript
// frontend/src/components/InterviewMode/ (重新實作)

[ ] InterviewLayout.tsx
    - 顯示當前章節背景
    - 顯示當前問題卡片
    - 顯示回答充分度指標（而非主題覆蓋率）
    - 顯示建議追問

[ ] QuestionCardDisplay.tsx
    - 顯示問題
    - 顯示預期回答要素
    - 顯示回答充分度分數
    - 顯示已回答 vs 未回答要素

[ ] SufficiencyIndicator.tsx (新建)
    - 視覺化回答充分度
    - 顏色編碼:
      - 紅色: insufficient (< 40%)
      - 黃色: partially_sufficient (40-70%)
      - 綠色: sufficient (> 70%)
```

#### 5.3 BRD 生成介面
```typescript
// frontend/src/routes/BRDGenerationPage.tsx (新建)

[ ] 訪談結束後的 BRD 生成頁面
[ ] 顯示:
    - 訪談完成度統計
    - 可用於生成 BRD 的問題列表
    - 「生成 BRD」按鈕
    - 生成進度指示器

// frontend/src/components/BRD/BRDPreview.tsx (新建)
[ ] BRD 預覽組件
    - Markdown 渲染
    - 章節導覽
    - 編輯功能
    - 匯出按鈕（Markdown / PDF）
```

---

### Phase 6: 測試與驗證 (優先級: P2)

#### 6.1 單元測試
```bash
[ ] tests/services/test_answer_evaluation_engine.py
[ ] tests/services/test_brd_generator_service.py
[ ] tests/api/test_interview_sessions.py
[ ] tests/api/test_brd_generation.py
```

#### 6.2 整合測試
```bash
[ ] tests/integration/test_full_interview_flow.py
    - 上傳需求文件
    - AI 分析並生成問題
    - 模擬訪談對話
    - 評估回答充分度
    - 生成 BRD

[ ] tests/integration/test_answer_evaluation.py
    - 測試各種回答情境
    - 驗證充分度計算邏輯
    - 驗證追問生成邏輯
```

#### 6.3 E2E 測試
```bash
[ ] cypress/e2e/document-upload.cy.ts
[ ] cypress/e2e/interview-session.cy.ts
[ ] cypress/e2e/brd-generation.cy.ts
```

---

## 📊 完成度評估矩陣

| 功能模組 | 文檔定義 | 資料模型 | API | 服務層 | 前端 | 測試 | 總計 |
|---------|---------|---------|-----|-------|------|------|------|
| 文件上傳 | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | 90% |
| 章節分析 | ✅ | ✅ | ✅ | 🟡 | 🟡 | ❌ | 60% |
| 問題生成 | ✅ | ✅ | ✅ | 🟡 | 🟡 | ❌ | 60% |
| 訪談會話 | ✅ | ✅ | ✅ | 🟡 | 🟡 | ❌ | 60% |
| 答案評估 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | 10% |
| BRD 生成 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | 0% |
| 即時轉錄 | ✅ | ✅ | ✅ | ✅ | 🟡 | ⚠️ | 75% |
| 報表分析 | ✅ | ✅ | ✅ | 🟡 | ⚠️ | ❌ | 50% |

**圖例**:
- ✅ 完成 (90-100%)
- ⚠️ 大部分完成 (70-89%)
- 🟡 部分完成 (40-69%)
- ❌ 未完成 (0-39%)

---

## 🎯 工作量估算

### 時間估算（以人日計）

| 階段 | 任務 | 工作量 | 優先級 |
|------|------|--------|--------|
| Phase 1 | 清理遺留代碼 | 3-5 天 | P0 |
| Phase 2 | 重構核心邏輯 | 10-15 天 | P0 |
| Phase 3 | 實作 Answer Evaluation | 8-12 天 | P0 |
| Phase 3 | 實作 BRD 生成 | 5-8 天 | P1 |
| Phase 4 | 資料庫重構 | 2-3 天 | P1 |
| Phase 5 | 前端重構 | 8-10 天 | P2 |
| Phase 6 | 測試與驗證 | 5-7 天 | P2 |
| **總計** | | **41-60 天** | |

**建議分配**:
- 1 位 Senior Backend Engineer: 20-25 天
- 1 位 Senior Frontend Engineer: 10-12 天
- 1 位 AI/ML Engineer: 8-10 天（Answer Evaluation + BRD Generation）
- 1 位 QA Engineer: 5-7 天

**總工時**: 約 **43-54 人日** (約 2-3 個月，假設 2-3 人同時開發)

---

## 🚨 風險與注意事項

### 風險 1: 架構債務
- **現狀**: 新舊系統並存，概念混亂
- **風險**: 每次開發都需要判斷用新的還是舊的，容易出錯
- **建議**: 儘快完成 Phase 1 清理，斬斷後路

### 風險 2: AI 邏輯差異
- **現狀**: 將「主題匹配」當成「答案評估」
- **風險**: 評估準確度低，用戶體驗差
- **建議**: 重新設計評估邏輯，可能需要調整 GPT prompt 和評分算法

### 風險 3: 資料遷移
- **現狀**: 開發過程中可能已有測試資料
- **風險**: 刪除舊表會導致資料遺失
- **建議**: 
  1. 確認是否有生產資料
  2. 如需保留，寫遷移腳本轉換到新表
  3. 否則直接清空重建

### 風險 4: 功能宣稱不實
- **現狀**: README 宣稱功能未實作
- **風險**: 誤導用戶或其他開發者
- **建議**: 更新 README，明確標示哪些功能已實作、哪些計劃中

---

## 📝 建議行動方案

### 立即行動（本週內）

1. **更新 README.md**
   ```markdown
   ## 🎯 目前狀態
   **實際完成度**: 35%
   
   ### 已完成
   - ✅ 品牌更名和文檔清理
   - ✅ 基礎資料模型（Document, Section, QuestionCard, InterviewSession）
   - ✅ 文件上傳與基礎 API
   - ✅ 即時轉錄整合
   
   ### 進行中
   - 🟡 Answer Evaluation Engine（計劃中）
   - 🟡 BRD 文件生成（計劃中）
   - 🟡 前端重構（部分完成）
   
   ### 未開始
   - ❌ 核心 AI 邏輯改造
   - ❌ 訪談模式完整實作
   - ❌ E2E 測試
   ```

2. **建立專案 Board**
   - 將上述 Phase 1-6 任務錄入 GitHub Issues / Jira
   - 標記優先級（P0/P1/P2）
   - 分配負責人

3. **代碼審查會議**
   - 與團隊一起過一遍這份評估報告
   - 討論技術方案
   - 確認工作量和排期

---

### 短期目標（2 週內）

**目標**: 完成 Phase 1 清理 + Phase 2 部分重構

**里程碑**:
- 刪除所有 SlideCue 遺留代碼
- Answer Evaluation Engine 基礎框架就位
- 至少一個完整的訪談流程可以跑通（即使評估邏輯還不完美）

---

### 中期目標（1.5 月內）

**目標**: 完成 Phase 2 + Phase 3 核心功能

**里程碑**:
- Answer Evaluation Engine 完整實作並測試
- BRD 生成功能基本可用
- 前端訪談模式可以正常使用
- 核心流程的整合測試通過

---

### 長期目標（3 個月內）

**目標**: 完成所有功能 + 測試 + 優化

**里程碑**:
- 前端完全重構
- E2E 測試覆蓋率 > 80%
- 性能優化
- 用戶文檔完善
- 準備 Beta 測試或內部試用

---

## 📄 附錄

### A. 關鍵檔案清單

#### 需要重構的檔案（高優先級）
```
backend/app/services/topic_matching_engine.py     ❌ 核心邏輯錯誤
backend/app/services/ai_card_generator.py         🟡 部分正確
backend/app/services/openai_service.py            🟡 部分正確
backend/app/services/semantic_judge_service.py    🟡 評估邏輯需改
backend/app/api/routes/events.py                  🟡 仍用舊模型
backend/app/api/routes/session_reports.py         🟡 概念混亂
frontend/src/components/PresenterMode/            ❌ 整個目錄概念錯誤
frontend/src/routes/EditorPage.tsx                🟡 UI 需調整
```

#### 需要刪除的檔案
```
backend/app/services/deck_service.py
backend/app/services/slide_service.py
backend/app/services/topic_card_service.py
backend/app/services/presentation_service.py
backend/app/models/presentation_session.py （部分）
frontend/src/stores/deckStore.ts
frontend/src/stores/presentationStore.ts
frontend/src/api/decks.ts
frontend/src/api/presentation.ts
frontend/src/components/PresenterMode/
```

#### 需要新建的檔案
```
backend/app/services/answer_evaluation_engine.py
backend/app/services/brd_generator_service.py
backend/app/api/routes/brd_generation.py
backend/app/models/brd_draft.py
backend/app/models/requirement.py
frontend/src/components/InterviewMode/ （完整實作）
frontend/src/components/BRD/
frontend/src/routes/BRDGenerationPage.tsx
```

---

### B. 技術債務清單

1. **代碼債務**
   - 新舊代碼並存（InterviewSession vs PresentationSession）
   - 大量註釋仍是 SlideCue 術語
   - 函數名與實際功能不符（analyze_slide 實際應處理 section）

2. **架構債務**
   - 核心業務邏輯未改變（Topic Matching ≠ Answer Evaluation）
   - 缺少關鍵服務（Answer Evaluation Engine, BRD Generator）
   - 資料庫 migrations 需要清理

3. **測試債務**
   - 幾乎沒有針對 InsightGuide 新邏輯的測試
   - 現有測試可能仍在測試 SlideCue 邏輯

4. **文檔債務**
   - README 宣稱功能未實作
   - 架構文檔與實際代碼不一致
   - 缺少 API 文檔更新

---

### C. 決策記錄

#### 為什麼不直接刪除所有舊代碼重寫？

**考慮因素**:
1. 保留部分可復用的基礎設施（DB, Redis, S3, 即時轉錄）
2. 減少風險：漸進式重構比一次性重寫更安全
3. 學習成本：可以參考 SlideCue 的實作經驗

**建議策略**:
- Phase 1 先清理明顯無用的代碼
- Phase 2-3 逐步重構核心邏輯
- 保留通用基礎設施（logging, config, database session）

---

## 📞 聯繫與協作

如有任何問題或需要進一步討論，請：
1. 在 GitHub 上開 Issue 討論具體技術方案
2. 在團隊會議上討論排期和資源分配
3. 更新這份文檔反映最新進展

---

**報告編寫**: Claude Code  
**審查狀態**: 待團隊審核  
**下次更新**: 完成 Phase 1 後

