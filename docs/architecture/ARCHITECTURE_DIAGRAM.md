# SlideCue Architecture Diagram

**Last Updated**: 2026-06-02
**Source Of Truth**: current backend/frontend implementation plus `docs/reports/SYSTEM_HEALTH_CHECK_REPORT.md`.

---

## System Overview

```text
┌────────────────────────────────────────────────────────────────────┐
│ Frontend: React + TypeScript + Vite                               │
│                                                                    │
│ DeckUploadPage  EditorPage  PresenterPage  Reports                │
│                                                                    │
│ Presenter Mode                                                     │
│ - useRealtimeTranscription: WebRTC transcription                   │
│ - useSSEEvents: Topic Card live updates                            │
│ - useScriptPlan: Smart Prompt cursor and regeneration              │
└───────────────────────────────┬────────────────────────────────────┘
                                │ HTTP + SSE + WebRTC
                                │
┌───────────────────────────────▼────────────────────────────────────┐
│ Backend: FastAPI                                                   │
│                                                                    │
│ /api/decks                  deck upload and analysis status         │
│ /api/slides                 slide data                             │
│ /api/topic-cards            card CRUD, cleanup, script regen        │
│ /api/prep-sessions          prep lifecycle and SSE                  │
│ /api/presentation-sessions  session, utterance, card state, report  │
│ /api/realtime               ephemeral token for WebRTC              │
│ /api/events                 presenter card-state SSE                │
│ /api/script-plan            Smart Prompt plan/cursor/regenerate     │
└───────────────────────────────┬────────────────────────────────────┘
                                │
┌───────────────────────────────▼────────────────────────────────────┐
│ Services                                                           │
│                                                                    │
│ presentation_service     persist sessions/utterances, publish SSE   │
│ topic_matching_engine    card progress, child aspect coverage       │
│ semantic_judge_service   GPT-5.4-mini judgments and cleanup         │
│ script_plan_service      Smart Prompt plan and cursor state         │
│ topic_card_service       card CRUD, metadata, script regeneration   │
│ openai_service           slide analysis and topic card generation   │
│ realtime_service         OpenAI Realtime transcription token        │
│ report_*_service         report analytics and export                │
│ deck/slide/s3 services   file, slide, and storage operations        │
└───────────────────────────────┬────────────────────────────────────┘
                                │
┌───────────────────────────────▼────────────────────────────────────┐
│ Data And Workers                                                   │
│                                                                    │
│ PostgreSQL + pgvector: decks, slides, cards, sessions, utterances   │
│ Redis + Celery: conversion, analysis, background jobs               │
│ MinIO/S3: uploaded decks, converted files, report exports           │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│ External AI Services                                               │
│                                                                    │
│ OpenAI Realtime Transcription: gpt-realtime-whisper via WebRTC      │
│ Slide analysis / topic cards: SLIDE_ANALYSIS_MODEL = gpt-5.5        │
│ Semantic judgment / Script Plan: SEMANTIC_UNDERSTANDING_MODEL       │
│   = gpt-5.4-mini                                                    │
│ Embeddings: text-embedding-3-large                                  │
└────────────────────────────────────────────────────────────────────┘
```

---

## Presenter Mode Data Flow

```text
1. User enters Presenter Mode
   -> DynamicScriptPanel auto-generates a Script Plan
   -> useRealtimeTranscription requests an ephemeral Realtime token
   -> Preparing overlay remains until microphone and prompt are ready

2. User speaks
   -> OpenAI Realtime sends transcript delta events
   -> UI displays pending transcript
   -> partial transcript is sent to /partial-transcript-match
   -> Topic Matching may update card water level through SSE

3. Realtime transcription completes an utterance
   -> frontend converts text to Traditional Chinese
   -> POST /api/presentation-sessions/{id}/utterances
   -> backend persists utterance and immediately returns
   -> backend schedules Topic Matching in background
   -> frontend triggers /api/script-plan/{id}/advance

4. Smart Prompt advances independently
   -> Script Plan cursor updates based on transcript vs current prompt
   -> manual 下一句 uses /api/script-plan/{id}/next
   -> regeneration uses uncovered cards, excluding cards already covered

5. Topic Cards update independently
   -> Topic Matching judges accumulated transcript context
   -> covered child aspect IDs drive bullet strikethrough and water level
   -> CARD_LISTENING / CARD_PROBABLY_COVERED / CARD_COVERED events update UI
```

---

## Card And Script Dependency Rule

Runtime dependency is intentionally one-way from transcript input into two independent processors:

```text
Transcript
  ├─> Script Plan advance -> Smart Prompt cursor
  └─> Topic Matching      -> Topic Card state/water/bullets
```

Do not reintroduce card-event-driven Script Plan advancement.

Allowed interactions:

- Script Plan generation and regeneration may read Topic Card definitions and current card states as planning context.
- Topic Matching may read utterance history and card coverage rules.
- Manual card status updates may update card evidence.

Disallowed interactions:

- `CARD_COVERED` should not call Script Plan `advance`.
- Topic Card water level should not directly move Script Plan cursor.
- Manual `下一句` should not mark Topic Cards covered.

---

## Topic Card Completion Model

Current card progress uses child aspect completion:

```text
required_aspect_ids = semanticAnchors + mustMentionFacts
card_progress = covered_required_aspect_ids / required_aspect_ids
```

Backend normalization:

- If GPT says a card is complete and no important aspects are missing, all required IDs are treated as covered.
- If GPT returns `missing_aspect_ids`, covered IDs are derived as `required - missing`.
- Frontend renders strikethrough only from `coveredAspectIds`.
- Water level is based on child aspect ratio when available.

---

## Smart Prompt / Script Plan

Active files:

- `backend/app/api/routes/script_plan.py`
- `backend/app/services/script_plan_service.py`
- `backend/app/services/semantic_judge_service.py`
- `frontend/src/hooks/useScriptPlan.ts`
- `frontend/src/components/PresenterMode/DynamicScriptPanel.tsx`

Current behavior:

- Generates a 12-sentence plan by default.
- Displays current and next prompt as "智慧題詞".
- Advances after saved completed transcripts.
- Supports manual `下一句`.
- Shows explicit completion state when cursor reaches total.
- Automatically regenerates only on repeated/off-topic progression signals.

---

## Removed / Inactive Historical Paths

The following are historical and should not be treated as active architecture:

- `backend/app/services/dynamic_script_generator.py`
- `backend/app/services/script_coverage_judge.py`
- `frontend/src/components/PresenterMode/SuggestedScriptPanel.tsx`
- `/api/realtime-script`
- `realtime_script_service.py` / `realtime_script.py` route mounting

Historical docs may still mention these paths for reference, but new implementation should follow the active Script Plan architecture above.

---

## Verification Gates

```bash
cd backend
DEBUG=false venv/bin/python -m compileall -q app tests
DEBUG=false venv/bin/python -m pytest -q
```

```bash
cd frontend
npm run lint
npm run build
```

```bash
curl -s http://localhost:8001/health
```
