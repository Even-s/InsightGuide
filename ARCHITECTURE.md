# InsightGuide Architecture

## Overview

InsightGuide is an AI-powered requirements interview assistant. It helps Business Analysts (BAs) conduct structured interviews by:

1. Analyzing uploaded BRD (Business Requirements Document) drafts
2. Generating interview themes and question cards with coverage rules
3. Providing real-time transcription and answer evaluation during interviews
4. Producing post-interview BRD documents and analytics reports

## System Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS |
| Backend | Python 3.11 + FastAPI + SQLAlchemy + Pydantic |
| Database | PostgreSQL |
| Cache/PubSub | Redis (SSE events, Celery broker) |
| Object Storage | MinIO (S3-compatible) |
| AI | OpenAI GPT-5.x family + Realtime API (WebRTC) |
| Task Queue | Celery (document analysis worker) |

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Vite)                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐   │
│  │  Upload  │  │  Editor  │  │Interview │  │    Report     │   │
│  │  Page    │  │  Page    │  │  Page    │  │    Page       │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬────────┘   │
│       │              │             │               │             │
│       │         REST API      WebRTC + REST    REST API          │
└───────┼──────────────┼─────────────┼───────────────┼────────────┘
        │              │             │               │
┌───────┼──────────────┼─────────────┼───────────────┼────────────┐
│       ▼              ▼             ▼               ▼            │
│                    FastAPI Backend (port 8002)                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                     API Routes                          │    │
│  │  documents | prep-sessions | interview-sessions | brd   │    │
│  │  question-cards | sections | realtime | events          │    │
│  └──────────────────────────┬──────────────────────────────┘    │
│                             │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐    │
│  │                    Services Layer                        │    │
│  │  ┌────────────────┐  ┌─────────────────────────────┐    │    │
│  │  │ Document       │  │ Answer Evaluation Engine     │    │    │
│  │  │ Analysis Flow  │  │  ├─ Semantic Judge (GPT)     │    │    │
│  │  │  ├─ Themes     │  │  ├─ Embedding Service       │    │    │
│  │  │  ├─ Cards      │  │  ├─ Scoring Service         │    │    │
│  │  │  └─ Coverage   │  │  └─ Hallucination Filter    │    │    │
│  │  └────────────────┘  └─────────────────────────────┘    │    │
│  │  ┌────────────────┐  ┌─────────────────────────────┐    │    │
│  │  │ BRD Generation │  │ Billing Service             │    │    │
│  │  │  ├─ Sections   │  │  ├─ Token cost tracking     │    │    │
│  │  │  ├─ AI Rewrite │  │  └─ Audio cost tracking     │    │    │
│  │  │  └─ Caching    │  └─────────────────────────────┘    │    │
│  │  └────────────────┘                                      │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
│  │PostgreSQL│  │  Redis   │  │  MinIO   │  │  OpenAI API  │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

## Data Model (Entity Relationships)

```
User
 ├── Document (1:N)
 │    ├── Section (1:N) — extracted pages/paragraphs from uploaded file
 │    ├── InterviewTheme (1:N) — AI-generated interview units
 │    │    └── QuestionCard (1:N) — questions with coverage rules
 │    │         ├── InterviewCardState (1:N per session)
 │    │         └── Requirement (0:N, from BRD generation)
 │    ├── PrepSession (1:1) — preparation container
 │    │    └── InterviewSession (1:N) — actual interview runs
 │    │         ├── InterviewCardState (1:N)
 │    │         ├── Utterance (1:N)
 │    │         ├── AIUsageEvent (1:N)
 │    │         └── BRDDraft (0:1)
 │    └── AIUsageEvent (1:N, deck-level costs)
 └── BRDDraft (1:N via interview sessions)
```

## Core Workflows

### 1. Document Upload & Analysis

```
User uploads PDF/DOCX
  → S3 storage
  → Celery worker: document_analysis_worker.py
    → Phase 1: generate_interview_themes() [GPT-4o]
       Analyzes full document, produces 8-13 interview themes
    → Phase 2: generate_theme_question_cards() [GPT-4o]
       For each theme, generates 3-6 focus topics × 1-3 questions
    → Saves InterviewTheme + QuestionCard records
  → SSE event: ANALYSIS_COMPLETE
```

### 2. Interview Session (Real-time)

```
User starts interview
  → Frontend: useRealtimeTranscription hook
    → WebRTC connection to OpenAI Realtime API
    → Ephemeral token from backend /api/realtime/token
  → Audio streamed directly to OpenAI (browser → OpenAI)
  → Transcript deltas received via WebRTC DataChannel
  → On completed utterance:
    Frontend → POST /api/interview-sessions/{id}/utterances
      → Speaker classification [GPT-5.4-mini]
      → Background task: process_utterance_evaluation
        → If interviewer: match question → activate card (pending → listening)
        → If interviewee: evaluate sufficiency [GPT-5.4-mini]
          → Update card state (listening → probably_sufficient → sufficient)
      → SSE event: CARD_COVERED / CARD_LISTENING / etc.
```

### 3. Answer Evaluation Pipeline

```
Utterance (interviewee) received
  → _load_candidate_cards: find listening cards for current theme
  → _get_answer_context_for_cards: build context window
  → _batch_judge_answer_sufficiency: one GPT call scores all candidates
  → _update_card_state:
      confidence < 0.3 → no change
      confidence ≥ 0.85 or is_covered → sufficient
      confidence ≥ 0.62 → probably_sufficient
      else → status unchanged (still listening)
```

### 4. BRD Generation (Post-Interview)

```
User opens report page
  → POST /api/interview-sessions/{id}/outputs/generate
  → Check BRDDraft cache (if exists, return immediately)
  → Build sections from card evidence + theme mapping
  → AI rewrite: raw evidence → formal BRD paragraphs [GPT]
  → Render markdown (BRD + transcript)
  → Persist to BRDDraft.markdown_content
  → Return structured result
```

## Frontend Architecture

### Pages (Routes)

| Route | Component | Purpose |
|-------|-----------|---------|
| `/` | DeckUploadPage | Upload BRD documents |
| `/prep-sessions` | PrepSessionListPage | Manage all prep sessions |
| `/editor/:deckId` | EditorPage | Review/edit themes & question cards |
| `/interview/:deckId` | PresenterPage | Live interview with transcription |
| `/interview/:deckId/report/:sessionId` | InterviewReportPage | BRD + transcript output |
| `/interview/:sessionId/brd` | BRDGenerationPage | Structured BRD editor |
| `/sessions` | SessionListPage | Historical session list |

### Key Hooks

| Hook | Purpose |
|------|---------|
| `useRealtimeTranscription` | WebRTC connection to OpenAI Realtime API |
| `usePresentationSession` | Interview session state, theme navigation |
| `useDeckEvents` | SSE subscription for document analysis progress |
| `useResponsiveLayout` | Adaptive layout for interview mode |

### Real-time Communication

- **SSE (Server-Sent Events)**: Backend → Frontend for card state updates, analysis progress
- **WebRTC**: Browser → OpenAI for audio streaming (transcription)
- **REST**: Frontend → Backend for utterance storage and evaluation triggers

## Backend Service Layer

### Core Services

| Service | Responsibility |
|---------|---------------|
| `openai_service` | All GPT API calls (analysis, classification, themes, cards) |
| `answer_evaluation_engine` | Utterance → card state updates (two-stage: embedding + AI judge) |
| `semantic_judge_service` | GPT-based coverage/sufficiency judgments |
| `brd_generation_service` | Post-interview BRD document assembly + AI rewrite |
| `billing_service` | Token/audio cost tracking per session and per document |
| `interview_service` | Session lifecycle, utterance CRUD, card state management |
| `document_service` | Document CRUD, file management |
| `event_service` | Redis pub/sub → SSE event distribution |
| `realtime_service` | OpenAI Realtime ephemeral token generation |

### Supporting Services

| Service | Responsibility |
|---------|---------------|
| `embedding_service` | text-embedding-3-large for semantic similarity |
| `scoring_service` | Confidence score normalization |
| `hallucination_filter` | Validates AI outputs against source material |
| `s3_service` | MinIO file upload/download |
| `prep_session_service` | Prep session lifecycle |
| `question_card_service` | Card CRUD and reordering |
| `section_service` | Document section management |
| `report_analytics_service` | Post-interview performance analytics |
| `report_export_service` | Report export formatting |
| `bullet_point_service` | Summarization service |
| `session_cleanup` | Stale session cleanup |

## AI Model Usage

| Model | Use Case | Latency Profile |
|-------|----------|----------------|
| GPT-5.5 | Document section analysis (highest quality) | High (~10s) |
| GPT-4o | Interview theme + question card generation | Medium (~5s) |
| GPT-5.4-mini | Speaker classification, answer evaluation, semantic judging | Low (~1s) |
| gpt-realtime-whisper | Live audio transcription via WebRTC | Real-time |
| text-embedding-3-large | Semantic similarity for card matching | Low (~200ms) |

## Key Design Decisions

1. **Theme-based interview structure**: Documents are analyzed into themes (not just pages), enabling logical interview flow regardless of document structure.

2. **Two-stage answer evaluation**: Fast embedding recall + deep AI judgment prevents unnecessary GPT calls while maintaining accuracy.

3. **WebRTC for transcription**: Audio goes directly from browser to OpenAI — backend never handles audio data, reducing latency and bandwidth.

4. **Card state machine**: `pending → listening → probably_sufficient → sufficient` provides granular progress tracking with interviewer activation as a gate.

5. **Coverage rules on cards**: Each question card has `semanticAnchors`, `expectedKeywords`, and `mustMentionElements` — enabling both AI and deterministic evaluation.

6. **BRD caching**: Generated BRD documents are persisted to avoid non-deterministic regeneration on repeated page visits.

7. **Cascade deletion via Document**: Document is the aggregate root. Deleting it cascades to all related data (themes, cards, sessions, utterances, BRDs, billing events).

## Directory Structure

```
InsightGuide/
├── backend/
│   ├── app/
│   │   ├── api/routes/          # FastAPI route handlers
│   │   ├── core/                # Config, security, logging
│   │   ├── db/                  # SQLAlchemy session, Alembic migrations
│   │   ├── models/              # SQLAlchemy ORM models
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── services/            # Business logic layer
│   │   └── workers/             # Celery background tasks
│   ├── scripts/                 # Utility scripts
│   └── tests/                   # Pytest test suite
├── frontend/
│   ├── src/
│   │   ├── api/                 # Axios API client modules
│   │   ├── components/          # React components
│   │   │   ├── common/          # Shared UI components
│   │   │   ├── EditorMode/      # Question card editor
│   │   │   ├── PresenterMode/   # Interview mode UI
│   │   │   ├── SessionReport/   # Post-interview report
│   │   │   └── sessions/        # Session management
│   │   ├── hooks/               # Custom React hooks
│   │   ├── routes/              # Page-level components
│   │   ├── stores/              # State management
│   │   ├── types/               # TypeScript type definitions
│   │   └── utils/               # Utility functions
│   └── vite.config.ts
└── scripts/
    └── integration_tests/       # End-to-end test scripts
```

## Infrastructure Dependencies

| Service | Default Port | Purpose |
|---------|-------------|---------|
| FastAPI | 8002 | Backend API server |
| Vite dev server | 5174 | Frontend dev server |
| PostgreSQL | 5432 | Primary database |
| Redis | 6379 | Event pub/sub + Celery broker |
| MinIO | 9000 | S3-compatible object storage |
| OpenAI API | — | AI inference (external) |
