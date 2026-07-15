# 訪談逐字稿、Q&A 與卡片主題匹配系統改進計劃書（歷史封存）

> 此文件描述已退役的 diarization 雙軌方案。自 2026-07-15 起，系統只保存
> Realtime transcript，舊 diarization、revision、alignment、speaker Q&A 資料表
> 已由破壞性 migration 移除。請以 `docs/ARCHITECTURE.md` 為現行架構依據。

> **Status: COMPLETED (2026-06)**
>
> The live/final transcript separation, card coverage evaluation with basis_type, Q/A reconstruction,
> and utterance alignment have all been implemented. This document is retained as historical reference
> for the design rationale behind the transcript and evaluation architecture.

## 1. 改版背景

目前系統支援兩個主要能力：

1. 訪談中透過 OpenAI Realtime API 產生即時逐字稿，並即時驅動卡片覆蓋判斷。
2. 訪談結束後，前端上傳 MediaRecorder 錄製的完整 webm 音檔，進行 gpt-4o-transcribe diarize，產生正式逐字稿並用於 BRD / 逐字稿報告生成。

目前流程雖然已能支援即時卡片標亮與正式報告生成，但仍存在幾個核心問題：

```text
1. Realtime 逐字稿與 diarized 逐字稿共用同一張 utterances 表，diarize 完成後直接刪除 Realtime 資料並重建，導致即時卡片覆蓋結果的 evidence 指向被刪除的 utterance。
2. 即時卡片覆蓋與正式卡片覆蓋沒有清楚分離，容易混淆 provisional 與 final 狀態。
3. 每筆 utterance 都觸發 GPT evaluation（gpt-5.4-mini），容易造成成本、延遲與狀態抖動。
4. 每次 evaluation 將同一 theme 下所有候選卡片送入 LLM，prompt 過長且容易混淆。
5. GPT 回傳格式不穩定（有時回 {"cards": [...]}，有時回 {"0": {...}, "1": {...}}），解析失敗時全部 fallback 為 confidence=0。
6. 目前主要知道「卡片有沒有 covered」，但訪談結束後還需要知道「每一題對方實際回答了什麼」。
7. 多個 background task 同時執行時，舊 evaluation 結果可能覆蓋新狀態。
8. partial transcript 尚未穩定，若直接影響正式狀態，容易造成誤判。
9. context window 通常只包含當前 utterance 文字（25-50 chars），遠小於代碼上限 2000 chars，資訊不足。
```

因此，下一版本需要重新設計整體資料流，將即時資料與正式資料分離，並將卡片匹配流程升級為：

```text
live transcript → provisional card coverage
final transcript → Q/A reconstruction + final card coverage + BRD/report
```

---

## 2. 改版目標

本次改版目標如下：

```text
1. 將即時逐字稿與正式逐字稿分開管理（新建 live_utterances 與 final_utterances 表）。
2. 保留 Realtime 逐字稿，不再直接刪除，以便 debug 與 traceability。
3. 將卡片覆蓋結果分成 provisional 與 final（新建 card_coverage_evaluations 表）。
4. 訪談結束後，用正式逐字稿重新跑 final card coverage。
5. 新增 Question-Answer Reconstruction，整理每一題受訪者實際回答。
6. 將卡片匹配流程從「全量 gpt-5.4-mini 判斷」改為「gpt-5.4-nano 初篩 + gpt-5.4-mini 精判 + deterministic reducer」。
7. partial transcript 只做即時 provisional match，不可產生 final sufficient。
8. 加入 evaluation_seq / versioned SSE，避免舊任務覆蓋新狀態。
9. 每個 final sufficient card 都必須有 evidence quote。
10. BRD / 報告生成只使用 final_utterances、question_answers 與 final_card_coverage。
```

核心設計原則：

```text
訪談中追求低延遲與即時互動。
訪談後追求準確性、可追溯性與正式輸出品質。
```

---

## 3. 現有系統基礎

以下為目前系統已存在的基礎設施，本次改版可直接利用：

```text
已存在：
- utterances 表（將拆分為 live_utterances + final_utterances）
- interview_card_states 表（將演進為 card_coverage_evaluations）
- answer_evaluation_engine（_batch_judge_answer_sufficiency，使用 gpt-5.4-mini）
- diarize_service（gpt-4o-transcribe，含 PCM→WAV 轉換）
- diarize endpoint（POST /api/realtime/diarize/{sessionId}，已支援音檔上傳 + recordingStartedAt）
- MediaRecorder 前端錄音（已實作於 PresenterLayout，訪談結束自動上傳）
- prompt_registry_service（evaluation prompt 可透過 registry 管理版本）
- billing_service / ai_usage_events（已追蹤每次 AI 呼叫的 token 與成本）
- event_service + SSE（即時推送卡片狀態變化至前端）
- embedding_service（已存在但未被 evaluation 使用）
```

---

## 4. 最終版整體架構

新版系統分成三條主線：

```text
1. 訪談中即時資料流
   Realtime transcript → live_utterances → provisional card coverage → SSE 即時標亮

2. 訪談後正式資料流
   audio diarize → transcript_revision → final_utterances → Q/A reconstruction → final card coverage

3. 報告輸出資料流
   final_utterances + question_answers + final_card_coverage → BRD / transcript report
```

整體流程如下：

```text
訪談中
Mic
→ WebRTC → OpenAI Realtime API
→ transcript completed / partial transcript
→ live_utterances
→ gpt-5.4-nano candidate prefilter
→ provisional card coverage
→ SSE 推送即時卡片狀態

同時
Mic → MediaRecorder（opus/webm）→ 背景錄音

訪談結束
完整 webm audio + recordingStartedAt
→ POST /api/realtime/diarize/{sessionId}
→ diarize_service.transcribe_chunk()（gpt-4o-transcribe）
→ transcript_revision
→ final_utterances
→ question-answer reconstruction（gpt-5.4-mini）
→ final card coverage（gpt-5.4-mini）
→ session finalized

報告生成
POST /api/interview-sessions/{sessionId}/outputs/generate
→ load final_utterances
→ load question_answers
→ load final_card_coverage
→ build transcript markdown / Q&A report / BRD
```

---

## 5. 資料責任分工

| 資料 | 表 | 用途 | 是否正式 | 狀態 |
|------|---|------|---------|------|
| Realtime transcript | `live_utterances`（新建） | 訪談中即時逐字稿、卡片暫定標亮 | 否 | 新建 |
| Partial transcript | 不入 DB | 即時提示 | 否 | 維持現狀 |
| Diarized transcript | `final_utterances`（新建） | 正式逐字稿、Q/A、BRD | 是 | 新建 |
| 即時卡片覆蓋 | `card_coverage_evaluations.basis_type=live`（新建） | UI provisional 狀態 | 否 | 新建 |
| 最終卡片覆蓋 | `card_coverage_evaluations.basis_type=final`（新建） | 報告與正式判斷 | 是 | 新建 |
| 每題回答 | `question_answers`（新建） | 每一題對方回答了什麼 | 是 | 新建 |
| 實際問句 | `question_instances`（新建） | 訪談中實際問出的問題 | 是 | 新建 |
| 轉寫版本 | `transcript_revisions`（新建） | 正式逐字稿版本管理 | 是 | 新建 |
| live/final 對齊 | `utterance_alignment`（新建） | debug 與 traceability | 輔助 | Phase 5 |

最重要的原則：

```text
live_utterances 不作為正式報告來源。
final_utterances 不承擔即時互動壓力。
card coverage 必須區分 provisional 與 final。
```

現有表的演進：

```text
utterances → 拆分為 live_utterances + final_utterances（舊表廢棄）
interview_card_states → 演進為 card_coverage_evaluations（加入 basis_type、evidence）
```

---

## 6. 新資料表設計

所有新表均需透過 Alembic migration 建立（放在 `backend/app/db/migrations/versions/`）。

### 6.1 `live_utterances`

用途：儲存 Realtime API 產生的即時逐字稿。

```sql
CREATE TABLE live_utterances (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES interview_sessions(id),

  realtime_event_id TEXT,
  transcript TEXT NOT NULL,

  speaker TEXT DEFAULT 'unknown',
  -- 訪談中不做語者辨識，統一標 unknown 或 interviewee

  started_at TIMESTAMP,
  ended_at TIMESTAMP,

  sequence_index INT NOT NULL,

  is_partial BOOLEAN DEFAULT FALSE,

  created_at TIMESTAMP DEFAULT now()
);
```

設計原則：

```text
1. 訪談中 Realtime completed transcript 寫入此表。
2. partial transcript 原則上不入 DB；若保留，需標 is_partial = true。
3. 不在訪談結束後刪除。
4. 只作為 provisional card coverage 與 debug 使用。
```

---

### 6.2 `transcript_revisions`

用途：管理正式逐字稿版本。

```sql
CREATE TABLE transcript_revisions (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES interview_sessions(id),

  source TEXT NOT NULL,
  -- diarized | manual_upload | corrected

  model TEXT,

  status TEXT NOT NULL,
  -- processing | completed | failed | superseded

  recording_started_at TIMESTAMP,
  audio_file_url TEXT,

  segment_count INT DEFAULT 0,
  error_message TEXT,

  created_at TIMESTAMP DEFAULT now(),
  completed_at TIMESTAMP
);
```

設計原則：

```text
1. 每次 diarize 都建立一個 revision。
2. 不直接覆蓋舊正式逐字稿。
3. 支援重新 diarize、人工修正與版本比對。
```

---

### 6.3 `final_utterances`

用途：儲存正式 diarized transcript。

```sql
CREATE TABLE final_utterances (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES interview_sessions(id),
  transcript_revision_id TEXT NOT NULL REFERENCES transcript_revisions(id),

  speaker_label TEXT NOT NULL,
  -- speaker_0 | speaker_1 | speaker_2（原始 diarize 標籤）

  speaker_role TEXT,
  -- interviewer | interviewee | unknown（系統內部使用，用於 Q/A reconstruction）

  speaker_display_name TEXT,
  -- Speaker 1 | Speaker 2（報告顯示用）

  transcript TEXT NOT NULL,

  start_seconds FLOAT,
  end_seconds FLOAT,

  started_at TIMESTAMP,
  ended_at TIMESTAMP,

  sequence_index INT NOT NULL,

  theme_id TEXT,
  confidence FLOAT,

  created_at TIMESTAMP DEFAULT now()
);
```

設計原則：

```text
1. final_utterances 是正式逐字稿來源。
2. BRD、Q/A reconstruction 與 final card coverage 都讀取此表。
3. final evidence 必須指向 final_utterances。
4. speaker_label 保留原始 diarize 結果（speaker_0, speaker_1...）。
5. speaker_display_name 用於報告顯示（Speaker 1, Speaker 2...）。
6. speaker_role 僅系統內部使用，用於 question detection。
```

---

### 6.4 `card_coverage_evaluations`

用途：儲存卡片覆蓋判斷，並區分 live / final。取代現有 `interview_card_states`。

```sql
CREATE TABLE card_coverage_evaluations (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES interview_sessions(id),
  card_id TEXT NOT NULL REFERENCES question_cards(id),

  basis_type TEXT NOT NULL,
  -- live | final

  transcript_revision_id TEXT,

  state TEXT NOT NULL,
  -- pending | listening | probably_sufficient | sufficient

  confidence FLOAT,

  covered_element_ids JSONB DEFAULT '[]',
  missing_element_ids JSONB DEFAULT '[]',
  evidence JSONB DEFAULT '[]',

  evaluation_seq INT NOT NULL,

  model TEXT,
  prompt_version TEXT,

  created_at TIMESTAMP DEFAULT now()
);
```

`evidence` 格式：

```json
[
  {
    "element_id": "e1",
    "utterance_table": "final_utterances",
    "utterance_id": "utt_xxx",
    "quote": "我們目前主要用 Excel 和 Slack 管理需求。"
  }
]
```

設計原則：

```text
1. basis_type = live：訪談中的暫定判斷（由 gpt-5.4-nano 產生）。
2. basis_type = final：正式逐字稿基礎上的最終判斷（由 gpt-5.4-mini 產生）。
3. 報告生成只讀 basis_type = final。
4. final sufficient 必須有 evidence quote。
```

---

### 6.5 `question_instances`

用途：記錄訪談中實際問出的問題。

```sql
CREATE TABLE question_instances (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES interview_sessions(id),

  source_question_id TEXT,
  -- 對應原始題目、卡片或 interview guide question

  theme_id TEXT,
  card_id TEXT,

  interviewer_utterance_id TEXT REFERENCES final_utterances(id),
  asked_text TEXT NOT NULL,

  normalized_question TEXT,

  question_type TEXT,
  -- main_question | follow_up | clarification

  started_at TIMESTAMP,
  ended_at TIMESTAMP,

  sequence_index INT,
  match_confidence FLOAT,

  created_at TIMESTAMP DEFAULT now()
);
```

設計原則：

```text
1. 記錄訪談中實際被問出口的問題。
2. 可對應原始題目、卡片或 theme。
3. 支援追問、臨場改問與跳題。
```

---

### 6.6 `question_answers`

用途：儲存每一題受訪者實際回答。

```sql
CREATE TABLE question_answers (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES interview_sessions(id),
  question_instance_id TEXT NOT NULL REFERENCES question_instances(id),

  answer_text TEXT,
  answer_summary TEXT,

  answer_utterance_ids JSONB DEFAULT '[]',
  evidence_quotes JSONB DEFAULT '[]',

  answer_status TEXT,
  -- answered | partially_answered | not_answered | unclear

  confidence FLOAT,

  created_at TIMESTAMP DEFAULT now()
);
```

設計原則：

```text
1. question_answers 回答「每一題對方實際講了什麼」。
2. answer_text 保留較完整答案。
3. answer_summary 用於報告與 BRD。
4. evidence_quotes 保留原文依據。
```

---

### 6.7 `utterance_alignment`（Phase 5）

用途：對齊 live_utterances 與 final_utterances。

```sql
CREATE TABLE utterance_alignment (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES interview_sessions(id),

  live_utterance_id TEXT REFERENCES live_utterances(id),
  final_utterance_id TEXT REFERENCES final_utterances(id),

  transcript_revision_id TEXT NOT NULL REFERENCES transcript_revisions(id),

  time_overlap_score FLOAT,
  text_similarity_score FLOAT,
  alignment_confidence FLOAT,

  created_at TIMESTAMP DEFAULT now()
);
```

此表可在 Phase 5 實作，非 MVP 必要。

---

## 7. Session 狀態欄位調整

在 `InterviewSession` model（`backend/app/models/interview_session.py`）新增欄位，並建立對應 Alembic migration：

```python
transcript_status = Column(String, nullable=False, default="live_only")
# live_only | diarizing | finalized | diarize_failed

final_transcript_revision_id = Column(String, ForeignKey("transcript_revisions.id"), nullable=True)

card_coverage_status = Column(String, nullable=False, default="provisional")
# provisional | finalizing | finalized | failed
```

---

## 8. API 調整

### 8.1 訪談中：寫入即時逐字稿

將現有 `POST /api/interview-sessions/{sessionId}/utterances` 改為寫入 `live_utterances`：

```http
POST /api/interview-sessions/{sessionId}/live-utterances
```

Payload（與現有格式相容）：

```json
{
  "transcript": "我們目前主要用 Excel 和 Slack 管理需求。",
  "speaker": "unknown",
  "startedAt": "2026-06-15T10:00:01.200Z",
  "endedAt": "2026-06-15T10:00:04.800Z",
  "sequenceIndex": 12,
  "realtimeItemId": "evt_xxx",
  "themeId": "optional-theme-id"
}
```

後端處理：

```text
1. 寫入 live_utterances。
2. 啟動 provisional card coverage evaluation（gpt-5.4-nano）。
3. 寫入 card_coverage_evaluations basis_type = live。
4. 透過 event_service SSE 推送前端即時狀態。
```

需修改的檔案：
- `backend/app/api/routes/interview_sessions.py`（endpoint 改名 + 改目標表）
- `backend/app/services/interview_service.py`（service layer）
- `backend/app/services/answer_evaluation_engine.py`（evaluation 讀取來源）

---

### 8.2 訪談中：partial transcript match

```http
POST /api/interview-sessions/{sessionId}/partial-transcript-match
```

維持現有 endpoint，但加入規則限制：

```text
1. partial transcript 不寫入 DB。
2. 不可產生 sufficient。
3. 不可成為 final evidence。
4. 只能觸發 listening / provisional_match。
```

---

### 8.3 訪談結束：正式 diarize

維持現有 endpoint：

```http
POST /api/realtime/diarize/{sessionId}
```

Payload（已實作）：

```text
multipart/form-data:
- audio: webm blob
- recording_started_at: ISO timestamp
```

後端處理調整為：

```text
1. 建立 transcript_revision（source=diarized, model=gpt-4o-transcribe）。
2. session.transcript_status = diarizing。
3. 執行 diarize_service.transcribe_chunk()。
4. 寫入 final_utterances（不再刪除 live_utterances）。
5. 設定 speaker_display_name（Speaker 1, Speaker 2...）。
6. 執行 question-answer reconstruction（gpt-5.4-mini）。
7. 執行 final card coverage（gpt-5.4-mini）。
8. session.transcript_status = finalized。
9. session.card_coverage_status = finalized。
```

需修改的檔案：
- `backend/app/api/routes/diarize.py`（改為寫入 final_utterances，不刪除 live）
- `backend/app/services/brd_generation_service.py`（改讀 final_utterances）

---

### 8.4 生成輸出

```http
POST /api/interview-sessions/{sessionId}/outputs/generate
```

後端處理調整為：

```text
1. 檢查 session.transcript_status == finalized。
2. 載入 final_utterances。
3. 載入 question_answers。
4. 載入 final card coverage。
5. 產生正式逐字稿、每題回答整理、卡片覆蓋報告與 BRD。
```

需修改的檔案：
- `backend/app/services/brd_generation_service.py`

---

## 9. 卡片主題匹配系統新版設計

### 9.1 新版卡片匹配核心流程

```text
utterance / partial transcript
→ debounce / end-of-turn detection
→ theme resolver
→ candidate prefilter（gpt-5.4-nano / embedding）
→ LLM judge（gpt-5.4-mini）
→ deterministic reducer
→ versioned SSE
```

---

### 9.2 觸發時機優化

目前每筆 utterance 都觸發完整 evaluation。新版改為：

```text
partial transcript:
- 只做 provisional match（gpt-5.4-nano）
- 不可標 sufficient
- 可用 nano 快速判斷

completed realtime utterance:
- debounce 500~1500ms
- 合併同 speaker 連續短 utterance
- 做 provisional evaluation（gpt-5.4-nano）

final utterances:
- diarize 完成後批次進行 final evaluation（gpt-5.4-mini）
```

---

### 9.3 Theme Resolver 優化

新版 theme 判斷順序：

```text
1. 若 utterance.themeId 存在，使用 utterance.themeId。
2. 若 session.current_theme_id 存在，使用 current_theme_id。
3. 若都不存在，使用 gpt-5.4-nano 或 embedding 做 theme classification。
4. 若 theme confidence 太低，標記為 uncertain_theme，不進行 sufficient 判斷。
```

不再直接 fallback 到第一個 enabled theme。

原因：

```text
錯誤完成卡片的代價高於暫時漏判。
```

---

### 9.4 Candidate Prefilter

目前系統有 `embedding_service` 但未被 evaluation 使用。新版啟用 embedding-based prefilter：

每張卡片建立 searchable text：

```text
card_search_text =
  focus_text
  + question_text
  + mustMentionElements
  + expectedKeywords
  + semanticAnchors
```

新流程：

```text
1. 建立 card embedding（可在 prep session 階段預先計算）。
2. 對 answer window 建立 embedding。
3. 計算 semantic similarity。
4. 加上 keyword / mustMentionElements hit score。
5. 加上 current question relevance。
6. 只取 top-K candidate cards。
7. 將 top-K 送入 LLM judge。
```

建議 top-K：

```text
一般情況：5~10 張
卡片少於 10 張：可全量送入
卡片多於 30 張：一定要 prefilter
```

---

### 9.5 Context 結構化

目前 `_get_answer_context_for_cards` 通常只取當前 utterance 文字（25-50 chars）。改為結構化 context：

```json
{
  "current_utterance": "...",
  "current_interviewer_question": "...",
  "recent_answer_window": "...",
  "relevant_prior_snippets": [
    {
      "utterance_id": "...",
      "text": "...",
      "reason": "matched card element"
    }
  ],
  "existing_card_coverage": {
    "card_id": "...",
    "covered_element_ids": []
  }
}
```

好處：

```text
1. 避免塞入過多無關上下文。
2. 可找回與該卡片相關的歷史回答。
3. 支援跨多輪回答的卡片判斷。
4. evidence 可精準指向 utterance。
```

---

### 9.6 LLM Judge 輸出格式

使用 `response_format={"type": "json_object"}` 強制 JSON 輸出（目前已使用但格式不穩定）。新版明確定義結構：

```json
{
  "evaluations": [
    {
      "card_id": "...",
      "decision": "not_covered | partial | probably_covered | covered",
      "confidence": 0.0,
      "covered_element_ids": [],
      "missing_element_ids": [],
      "evidence": [
        {
          "element_id": "...",
          "utterance_id": "...",
          "quote": "逐字稿中的原文片段"
        }
      ],
      "suggested_followup": "..."
    }
  ]
}
```

重要規則：

```text
1. 沒有 evidence quote，不可標 covered。
2. partial transcript 不可標 sufficient。
3. missing required element 時，不可標 sufficient。
4. confidence 只作為輔助，不作為唯一依據。
5. final coverage evidence 必須指向 final_utterances。
6. prompt 明確要求回傳 "evaluations" key（避免格式不穩定問題）。
```

---

### 9.7 Deterministic Reducer

LLM 不直接決定資料狀態，而是由 reducer 根據 LLM 結果與系統規則轉換狀態。

狀態流：

```text
pending
→ listening
→ probably_sufficient
→ sufficient
→ locked
```

建議規則：

```text
pending → listening:
- semantic_score 高
- 或 LLM decision = partial

listening → probably_sufficient:
- 有部分 required elements 被 evidence 覆蓋
- confidence 達中等門檻

probably_sufficient → sufficient:
- 所有 required elements 均有 evidence
- confidence 達高門檻
- 來源不是 partial transcript

sufficient → locked:
- 狀態穩定一段時間
- 或訪談進入下一個 theme
```

建議初始 threshold：

```text
nano_score < 0.35:
  明顯無關，不呼叫 mini

nano_score >= 0.35:
  送 mini 精判

mini confidence >= 0.82 且 required elements 全部有 evidence:
  sufficient

mini confidence >= 0.65 且有部分 covered elements:
  probably_sufficient

semantic_score 高但 required elements 不完整:
  listening
```

---

### 9.8 Race Condition 與 Versioned SSE

每次 evaluation job 需帶：

```text
session_id
theme_id
basis_type
from_utterance_id
to_utterance_id
transcript_revision_id
evaluation_seq
created_at
```

DB 更新時應避免舊 evaluation 覆蓋新結果：

```sql
UPDATE card_coverage_evaluations
SET ...
WHERE card_id = ?
AND session_id = ?
AND evaluation_seq < ?
```

SSE 事件透過現有 `event_service` 推送，新增 version 欄位：

```json
{
  "type": "CARD_STATE_PATCH",
  "basisType": "live",
  "cardId": "...",
  "state": "probably_sufficient",
  "confidence": 0.74,
  "coveredElementIds": ["e1", "e2"],
  "evidence": [],
  "evaluationSeq": 42
}
```

前端只接受比目前新的 `evaluationSeq`。

---

## 10. 模型分工策略

### gpt-5.4-nano 用途

```text
1. partial transcript 即時提示。
2. theme 初判。
3. candidate card top-K 初篩。
4. 明顯無關 utterance 過濾。
5. provisional card match（basis_type=live）。
```

### gpt-5.4-mini 用途

```text
1. final card coverage（basis_type=final）。
2. mustMentionElements 覆蓋判斷。
3. evidence quote 抽取。
4. Q/A reconstruction。
5. answer summarization。
6. suggested_followup 產生。
```

原則：

```text
gpt-5.4-nano 負責高頻、低風險、非正式判斷。
gpt-5.4-mini 負責低頻、高風險、正式判斷。
```

不建議讓 nano 單獨決定：

```text
1. sufficient。
2. final coverage。
3. mustMentionElements 是否完整覆蓋。
4. 高風險灰區狀態轉移。
```

---

## 11. Question-Answer Reconstruction 設計

### 11.1 目的

Q/A reconstruction 回答的是：

```text
每一題問了什麼？
誰問的？
受訪者回答了什麼？
答案是否完整？
有哪些原文依據？
```

它與 card coverage 不同：

| 流程 | 目的 | 產物 |
|------|------|------|
| Card Coverage | 判斷卡片是否被涵蓋 | `card_coverage_evaluations` |
| Q/A Reconstruction | 整理每題回答 | `question_answers` |

---

### 11.2 Q/A Reconstruction 流程

```text
final_utterances
→ speaker role mapping
→ question detection
→ question-to-card matching
→ answer span extraction
→ answer summarization
→ question_answers
```

---

### 11.3 Speaker Role Mapping

diarize 回傳的是 `speaker_0`、`speaker_1`、`speaker_2`...

報告輸出統一用 Speaker 1、Speaker 2、Speaker 3 標注。Q/A reconstruction 內部需要判斷哪位是 interviewer（用於 question detection），但此角色標記僅為系統內部使用（`final_utterances.speaker_role`），不影響逐字稿顯示。

建議策略：

```text
1. MVP：訪談結束後讓使用者確認 speaker role（UI 提示）。
2. 系統輔助判斷：問句比例高者為 interviewer，回答較長者為 interviewee。
3. 使用者確認後寫入 final_utterances.speaker_role。
4. 若使用者跳過確認，系統使用啟發式判斷自動填入。
```

---

### 11.4 Question Detection

從 speaker_role = interviewer 的 utterances 中找出問題。

判斷條件：

```text
1. speaker_role = interviewer。
2. 句子含疑問詞或語意上是提問。
3. 要求對方描述、說明、確認、補充或比較。
```

輸出：寫入 `question_instances`。

---

### 11.5 Question-to-Card Matching

將實際問句對應到原始卡片或訪談題目。

比對來源：

```text
card.question_text
card.focus_text
card.mustMentionElements
card.semanticAnchors
theme_id
```

若無法對應，仍建立 `question_instance`，但 `card_id = null`。

---

### 11.6 Answer Span Extraction

基本規則：

```text
從 interviewer 的主問題開始，
擷取後續 interviewee 的連續發言，
直到下一個 interviewer 主問題出現。
```

MVP 規則：

```text
主問題後，到下一個主問題前的 interviewee 發言，視為該題答案。
```

---

### 11.7 Answer Summarization

每個 answer span 由 gpt-5.4-mini 產生：

```text
1. answer_text：完整答案文本。
2. answer_summary：報告用摘要。
3. evidence_quotes：原文依據。
4. answer_status：answered / partially_answered / not_answered / unclear。
5. confidence：判斷信心。
```

---

## 12. 訪談中與訪談後 UI 調整

### 12.1 訪談中 UI

資料來源：

```text
live_utterances
provisional card coverage（basis_type=live）
```

文案建議：

```text
可能已涵蓋
正在回答
暫定匹配
可能相關
```

避免使用：

```text
正式涵蓋
已完成
已回答
```

---

### 12.2 訪談結束後 UI

資料來源：

```text
final_utterances
question_answers
final card coverage（basis_type=final）
```

顯示內容：

```text
1. 正式逐字稿（Speaker 1, Speaker 2...）。
2. Speaker 角色確認（系統內部用，不影響顯示）。
3. 每題回答整理。
4. final card coverage。
5. BRD / report。
```

Speaker role confirmation UI：

```text
Speaker 1:「那我想先了解你們目前怎麼管理需求？」
Speaker 2:「我們現在主要是用 Excel 和 Slack...」

請確認：
Speaker 1 = 訪談者（用於問題偵測）
Speaker 2 = 受訪者
```

---

## 13. 最終輸出格式

### 13.1 正式逐字稿

```markdown
## 正式逐字稿

**Speaker 1** `00:00:12`
> 那我想先了解你們目前怎麼管理需求？

**Speaker 2** `00:00:16`
> 我們目前主要是用 Excel 和 Slack...
```

---

### 13.2 每題回答整理

```markdown
## 每題回答整理

### Q1. 你們目前怎麼管理需求？

**回答摘要**
受訪者表示目前主要使用 Excel 和 Slack 管理需求，部分內容會記錄在 Notion，但缺少統一的追蹤流程。

**原文依據**
> 我們目前主要是用 Excel 和 Slack。
> 有時候 PM 會另外開 Notion，但大家不一定會同步更新。

**回答狀態**
已回答
```

---

### 13.3 卡片覆蓋報告

```markdown
## 卡片覆蓋狀態

### 需求管理流程

狀態：已涵蓋

涵蓋要素：
- 目前工具
- 協作方式
- 版本管理痛點

缺少要素：
- 無

原文依據：
> 我們目前主要是用 Excel 和 Slack。
> 最大的問題是版本常常對不起來。
```

---

## 14. 實作階段規劃

### Phase 1：資料流分離

目標：將即時逐字稿與正式逐字稿拆開。

工作項目：

```text
1. 新增 Alembic migration：建立 live_utterances、transcript_revisions、final_utterances。
2. 現有 POST /.../utterances endpoint 改為寫入 live_utterances。
3. diarize endpoint 改為寫入 final_utterances（不再刪除 live_utterances）。
4. generate_outputs 改讀 final_utterances。
5. InterviewSession model 新增 transcript_status、final_transcript_revision_id。
```

需修改的檔案：

```text
backend/app/db/migrations/versions/006_*.py（新 migration）
backend/app/models/（新增 live_utterance.py、final_utterance.py、transcript_revision.py）
backend/app/api/routes/interview_sessions.py（endpoint 改名 + 改目標表）
backend/app/services/interview_service.py（改寫入目標）
backend/app/api/routes/diarize.py（改寫入 final_utterances）
backend/app/services/brd_generation_service.py（改讀取來源）
backend/app/models/interview_session.py（新增欄位）
```

驗收標準：

```text
1. 訪談中可正常即時顯示逐字稿。
2. 訪談後 final_utterances 可正確產生。
3. 報告生成不再依賴 live_utterances。
4. Realtime utterances 不會被刪除。
```

---

### Phase 2：卡片覆蓋分 provisional / final

目標：避免即時判斷與正式判斷混淆。

工作項目：

```text
1. 新增 Alembic migration：建立 card_coverage_evaluations。
2. answer_evaluation_engine 改寫入 card_coverage_evaluations（basis_type=live）。
3. diarize 完成後觸發 final card coverage（basis_type=final）。
4. generate_outputs 改讀 basis_type=final。
5. SSE event 加上 basisType 與 evaluationSeq。
6. 前端忽略舊 evaluationSeq。
```

需修改的檔案：

```text
backend/app/db/migrations/versions/007_*.py
backend/app/models/card_coverage_evaluation.py（新增）
backend/app/services/answer_evaluation_engine.py
backend/app/api/routes/diarize.py
backend/app/services/brd_generation_service.py
frontend/src/hooks/useSSEEvents.ts
```

驗收標準：

```text
1. 即時卡片標亮不會被當成正式結果。
2. final card coverage evidence 指向 final_utterances。
3. 舊 evaluation 不會覆蓋新狀態。
4. 報告中只出現 final coverage。
```

---

### Phase 3：卡片匹配流程優化

目標：降低成本、延遲與誤判。

工作項目：

```text
1. partial transcript 只做 provisional，不可 sufficient（修改 answer_evaluation_engine）。
2. evaluation job 加 evaluation_seq。
3. 實作 theme resolver（取代 fallback to first theme）。
4. 建立 card searchable text + card embedding（啟用現有 embedding_service）。
5. 實作 candidate top-K prefilter。
6. LLM judge prompt 強制回傳 "evaluations" key。
7. 加入 evidence quote requirement。
8. 實作 deterministic reducer。
9. provisional evaluation 改用 gpt-5.4-nano。
10. final evaluation 維持 gpt-5.4-mini。
```

需修改的檔案：

```text
backend/app/services/answer_evaluation_engine.py（主要重構）
backend/app/services/embedding_service.py（啟用 card embedding）
backend/app/services/openai_service.py（新增 nano 呼叫）
```

驗收標準：

```text
1. 每次 LLM judge 的候選卡片控制在 top-K。
2. final sufficient 必須有 evidence quote。
3. missing required element 不可 sufficient。
4. partial transcript 不可 sufficient。
5. API cost per session 下降。
6. p95 evaluation latency 下降。
7. false positive rate 下降。
```

---

### Phase 4：Q/A Reconstruction

目標：產生「每一題對方回答了什麼」。

工作項目：

```text
1. 新增 Alembic migration：建立 question_instances、question_answers。
2. 新增 models。
3. 實作 speaker role mapping（啟發式 + 使用者確認 UI）。
4. 實作 question detection（gpt-5.4-mini）。
5. 實作 question-to-card matching。
6. 實作 answer span extraction。
7. 實作 answer summarization（gpt-5.4-mini）。
8. generate_outputs 加入 question_answers 區塊。
9. 前端新增 speaker role confirmation UI。
```

需修改/新增的檔案：

```text
backend/app/db/migrations/versions/008_*.py
backend/app/models/question_instance.py（新增）
backend/app/models/question_answer.py（新增）
backend/app/services/qa_reconstruction_service.py（新增）
backend/app/services/brd_generation_service.py
backend/app/api/routes/diarize.py（觸發 Q/A reconstruction）
frontend/src/components/SpeakerRoleConfirmation.tsx（新增）
```

驗收標準：

```text
1. 系統可列出訪談中實際問出的問題。
2. 每題可看到受訪者回答摘要。
3. 每題答案有 evidence quotes。
4. 問題可對應到原始 card / theme。
5. 報告中可輸出 Q/A 區塊。
```

---

### Phase 5：live / final alignment

目標：提升 debug 與可追溯能力。

工作項目：

```text
1. 新增 Alembic migration：建立 utterance_alignment。
2. 使用時間重疊建立初版 alignment。
3. 加入 embedding similarity。
4. 後台顯示 live coverage 與 final coverage 差異。
```

---

### Phase 6：觀測與品質評估

目標：建立準確率、成本與延遲監控。

利用現有 `ai_usage_events` 表與 `billing_service`，擴展記錄：

```text
1. nano vs mini 呼叫次數與成本。
2. candidate card 數量 per evaluation。
3. nano top-K 命中率。
4. provisional coverage 與 final coverage 差異。
5. diarize processing time。
6. Q/A reconstruction latency。
7. 人工修正次數。
```

可透過現有 `prompt_registry_service` 追蹤 prompt_version。

---

## 15. 風險與對策

### 15.1 Speaker mapping 錯誤

風險：speaker_0 / speaker_1 角色判斷錯誤，導致問題與答案切分錯誤。

對策：MVP 階段加入人工確認 speaker role。speaker_role 僅影響 Q/A reconstruction，不影響逐字稿顯示。

---

### 15.2 問題與答案切分不準

風險：真實訪談中有追問、打斷與跳題，簡單規則可能切錯答案範圍。

對策：先用規則建立初版，再用 gpt-5.4-mini 判斷主問題、追問與答案歸屬。

---

### 15.3 即時覆蓋與正式覆蓋不一致

風險：訪談中顯示可能已涵蓋，但正式逐字稿重跑後未涵蓋。

對策：

```text
1. UI 明確標示訪談中結果為 provisional。
2. 正式報告只使用 final coverage。
3. 保留 live/final alignment 供 debug（Phase 5）。
```

---

### 15.4 LLM false positive

風險：模型過度推論，將未完整回答的卡片標成 sufficient。

對策：

```text
1. 沒有 evidence quote 不可 sufficient。
2. missing required element 不可 sufficient。
3. partial transcript 不可 sufficient。
4. sufficient 狀態由 deterministic reducer 控制。
```

---

### 15.5 Background task race condition

風險：舊 evaluation 晚於新 evaluation 回來，覆蓋較新的卡片狀態。

對策：

```text
1. evaluation_seq。
2. DB update 加版本檢查。
3. SSE event 帶 evaluationSeq。
4. 前端忽略舊 version。
```

---

### 15.6 Diarize 失敗或耗時過長

風險：訪談結束後無法即時產生正式逐字稿。

對策：

```text
1. session.transcript_status = diarize_failed。
2. 前端顯示重試按鈕。
3. 保留 audio file 與 live_utterances。
4. 支援重新 diarize。
```

---

### 15.7 GPT 回傳格式不穩定

風險：LLM 回傳的 JSON 結構不符合預期（已發生過）。

對策：

```text
1. prompt 中明確指定 "evaluations" 為唯一 top-level key。
2. 使用 response_format={"type": "json_object"}。
3. 解析時支援多種 fallback 格式（array、dict-with-index-keys）。
4. 透過 prompt_registry_service 追蹤 prompt 版本與成功率。
```

---

## 16. 優先實作順序

```text
Phase 1（資料流分離）：
1. live_utterances / final_utterances / transcript_revisions 建表。
2. endpoint 改名，live 寫入 live_utterances。
3. diarize 改寫入 final_utterances。
4. generate_outputs 改讀 final_utterances。

Phase 2（卡片覆蓋分離）：
5. card_coverage_evaluations 建表 + basis_type。
6. partial transcript 不可 sufficient。
7. evaluation_seq / versioned SSE。
8. diarize 後重跑 final card coverage。

Phase 3（匹配流程優化）：
9. card embedding + top-K prefilter。
10. evidence quote requirement。
11. deterministic reducer。
12. provisional evaluation 改用 gpt-5.4-nano。

Phase 4（Q/A Reconstruction）：
13. speaker role confirmation UI。
14. question_instances / question_answers 建表。
15. Q/A reconstruction pipeline。

Phase 5（Alignment & Debug）：
16. utterance_alignment。
17. live vs final coverage 差異分析。

Phase 6（觀測）：
18. 品質指標與成本監控。
```

MVP 最小可行版本：

```text
Phase 1 全部 + Phase 2 全部 + speaker role confirmation + 基礎 Q/A reconstruction
```

---

## 17. 總結

本次改版的核心不是單純更換模型，而是重建整個訪談資料生命週期與卡片判斷責任分工。

新版系統結構：

```text
live_utterances：
  負責訪談中的即時體驗。
  不刪除、不作為正式來源。

final_utterances：
  負責正式逐字稿、Q/A、BRD 與 final card coverage。
  由 gpt-4o-transcribe diarize 產生。

card_coverage_evaluations：
  區分 basis_type=live（gpt-5.4-nano）與 basis_type=final（gpt-5.4-mini）。

question_answers：
  負責回答「每一題對方實際講了什麼」。

transcript_revisions：
  負責正式逐字稿版本管理。

utterance_alignment（Phase 5）：
  負責 live 與 final 之間的 traceability。
```

模型責任分工：

```text
gpt-5.4-nano：
  高頻、低風險、非正式的即時判斷。
  provisional card match、theme classification、candidate prefilter。

gpt-5.4-mini：
  低頻、高風險、正式的語意判斷。
  final card coverage、Q/A reconstruction、evidence extraction、BRD rewrite。

gpt-4o-transcribe：
  音檔轉寫 + 語者辨識。

deterministic reducer：
  最終狀態轉移，避免模型直接控制資料狀態。
```

最終系統同時支援：

```text
1. 訪談中即時卡片標亮（gpt-5.4-nano，provisional）。
2. 訪談後正式 speaker-aware 逐字稿（Speaker 1, 2, 3...）。
3. 每題回答整理（Q/A reconstruction）。
4. 最終卡片覆蓋判斷（gpt-5.4-mini，final + evidence）。
5. BRD 與正式報告生成。
6. evidence 追溯與 debug。
7. 更低成本、更低延遲與更穩定的 UI 狀態。
```
