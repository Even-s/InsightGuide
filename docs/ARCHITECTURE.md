# InsightGuide Architecture

## Overview

InsightGuide is an AI-powered requirements interview assistant. It helps Business Analysts (BAs) conduct structured interviews by:

1. Analyzing uploaded BRD (Business Requirements Document) drafts
2. Generating interview themes and question cards with coverage rules
3. Providing real-time transcription and answer evaluation during interviews
4. Producing post-interview insight memos, evidence matrices, and BRD documents

## System Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS + Zustand |
| Backend | Python 3.11 + FastAPI + SQLAlchemy + Pydantic |
| Database | PostgreSQL + pgvector |
| Cache/PubSub | Redis (SSE events, Celery broker) |
| Object Storage | MinIO (S3-compatible) |
| AI | OpenAI GPT-5.x family + Realtime API (WebRTC) |
| Task Queue | Celery (document analysis worker) |

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Vite)                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐   │
│  │  Upload  │  │  Editor  │  │Interview │  │   Project     │   │
│  │  Page    │  │  Page    │  │  Page    │  │   Dashboard   │   │
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
│  │  projects | evidence-matrix | insight-memos | realtime  │    │
│  │  question-cards | sections | events | session-reports   │    │
│  └──────────────────────────┬──────────────────────────────┘    │
│                             │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐    │
│  │                    Services Layer                        │    │
│  │  ┌────────────────┐  ┌─────────────────────────────┐    │    │
│  │  │ Document       │  │ Answer Evaluation Engine     │    │    │
│  │  │ Analysis Flow  │  │  ├─ Semantic Judge (GPT)     │    │    │
│  │  │  ├─ Themes     │  │  ├─ Keyword/ngram Prefilter │    │    │
│  │  │  ├─ Cards      │  │  ├─ Criterion Ledger       │    │    │
│  │  │  └─ Coverage   │  │  └─ State Reducer           │    │    │
│  │  └────────────────┘  └─────────────────────────────┘    │    │
│  │  ┌────────────────┐  ┌─────────────────────────────┐    │    │
│  │  │ Post-Interview │  │ Project-Level Analysis      │    │    │
│  │  │  ├─ Insight    │  │  ├─ Stakeholder Plan        │    │    │
│  │  │  │   Memo      │  │  ├─ Evidence Matrix         │    │    │
│  │  │  ├─ Round      │  │  ├─ BRD Readiness          │    │    │
│  │  │  │  Aggregate  │  │  └─ Role Filter            │    │    │
│  │  │  └─ BRD Gen    │  │                             │    │    │
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
 ├── Project (1:N) — multi-interview container
 │    ├── StakeholderSlot (1:N) — AI-suggested role requirements
 │    │    └── StakeholderProfile (1:N) — actual interviewees
 │    │         └── InterviewSeries (1:N) — one topic across repeated interviews
 │    │              └── InterviewRound (1:N) — an immutable guide/question version
 │    │                   ├── Document (1:1) — guide document selected for this round
 │    │                   ├── InterviewSession (0:N) — resumable visits in one round
 │    │                   ├── InterviewInsightMemo (0:N) — one per visit; latest memo is cumulative
 │    │                   └── InterviewRoundAggregate (0:1) — canonical latest memo/snapshots
 │    ├── InterviewInsightMemo (1:N) — post-interview analysis
 │    ├── RequirementEvidenceMatrix (0:1) — cross-interview consolidation
 │    │    └── EvidenceMatrixEntry (1:N) — candidate requirements
 │    └── BRDReadinessReport (0:N) — generation readiness checks
 │
 ├── Document (1:N)
 │    ├── Section (1:N) — extracted pages/paragraphs from uploaded file
 │    ├── InterviewTheme (1:N) — AI-generated interview units
 │    │    └── QuestionCard (1:N) — questions with coverage rules
 │    │         ├── InterviewCardState (1:N per session)
 │    │         ├── CardCoverageEvaluation (1:N, Realtime transcript only)
 │    │         └── CardCriterionEvidence (1:N)
 │    ├── PrepSession (1:1) — preparation container
 │    │    └── InterviewSession (1:N) — actual interview runs
 │    │         ├── InterviewCardState (1:N)
 │    │         ├── LiveUtterance (1:N) — canonical Realtime transcript
 │    │         ├── InterviewBrief (0:1) — pre-interview guide
 │    │         ├── AIUsageEvent (1:N)
 │    │         └── BRDDraft (0:1)
 │    └── AIUsageEvent (1:N, document-level costs)
 └── BRDDraft (1:N via interview sessions)
```

## Core Workflows

### 1. Document Upload & Analysis

```
User uploads PDF/DOCX/Markdown
  → S3 storage
  → Celery worker: document_analysis_worker.py
    → Phase 1: generate_interview_themes() [GPT-4o]
       Analyzes the full document and requests 5-8 interview themes
    → Phase 2: generate_theme_question_cards() [GPT-4o]
       For each theme, requests 2-4 focused question cards
    → Saves InterviewTheme + QuestionCard records
  → SSE event: ANALYSIS_COMPLETE
```

### 2. Interview Session (Real-time)

```
User selects a stakeholder and topic series
  → Creates a new InterviewRound with objective, generation mode, and source sessions
  → Generates a new Document + PrepSession + Themes + QuestionCards
  → Once a session is created, the guide Document becomes immutable
  → Historical rounds keep their cards, transcripts, completion state, and insight memo unchanged

User starts interview
  → Frontend: useRealtimeTranscription hook
    → WebRTC connection to OpenAI Realtime API
    → Ephemeral token from backend /api/realtime/token
  → Audio streamed directly to OpenAI (browser → OpenAI)
  → Transcript deltas received via WebRTC DataChannel
  → On completed utterance:
    Frontend → POST /api/interview-sessions/{id}/utterances
      → Background task: process_utterance_evaluation
        → Match questions and evaluate answer sufficiency [GPT-5.4-mini]
        → Update card state (pending → listening → probably_sufficient → sufficient)
      → SSE event: CARD_COVERED / CARD_LISTENING / etc.
```

### 3. Answer Evaluation Pipeline

```
Realtime utterance received
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

### 5. Post-Interview Pipeline

```
Interview ends
  → Stop the Realtime connection and close the session
  → Reuse live_utterances as the complete transcript
  → Insight Memo Generation
    → Pain points, requirement candidates, constraints, unresolved questions
    → Memo is linked to InterviewRound and InterviewSeries
    → Rebuild the InterviewRound Aggregate from the round's latest cumulative memo
    → Multi-round insight views read one current aggregate memo per InterviewRound
  → Stakeholder Plan Update (dynamic interview suggestions)
  → Evidence Matrix Update from current Round Aggregates (if project-level)
  → BRD Generation (from Realtime transcript and card-state evidence)
```

### 6. Project-Level Analysis

```
Project Dashboard
  ├── Stakeholder Plan (AI-suggested roles + status tracking)
  ├── Interview Progress (sessions completed, memos generated)
  ├── Evidence Matrix (cross-interview requirement deduplication)
  │    ├── Validation status: candidate | validated | conflicted | needs_more_evidence
  │    ├── Stakeholder agreement: unanimous | majority | single_source | conflicted
  │    └── Missing validation tracking → drives interview suggestions
  └── BRD Readiness (readiness_score 0-1, mode: full | partial | not_ready)
       └── Generation gate: checks evidence sufficiency before BRD creation
```

## Frontend Architecture

### Pages (Routes)

| Route | Component | Purpose |
|-------|-----------|---------|
| `/` | HomePage | Home with new-project and project-management entrances |
| `/projects/new` | DocumentUploadPage | Create a project and upload requirement documents |
| `/projects` | ProjectSessionsPage | Project-centric session management |
| `/projects/:projectId` | ProjectDetailPage | Stakeholder plan, guides, readiness |
| `/projects/:projectId/evidence-matrix` | EvidenceMatrixPage | Cross-stakeholder requirement validation |
| `/projects/:projectId/readiness` | BRDReadinessPage | BRD generation feasibility check |
| `/prep-sessions` | PrepSessionListPage | Manage all prep sessions (admin) |
| `/editor/:documentId` | EditorPage | Review/edit themes & question cards |
| `/interview/:documentId` | PresenterPage | Live interview with transcription |
| `/interview/session/:sessionId` | PresenterPage | Resume interview by session |
| `/interview/:documentId/report/:sessionId` | InterviewReportPage | Post-interview analytics |
| `/interview/:sessionId/brd` | BRDGenerationPage | Structured BRD editor |
| `/sessions/:sessionId/insight-memo` | InsightMemoPage | Post-interview qualitative analysis |
| `/sessions/:sessionId/log` | SessionLogPage | Event timeline |

### Repeated Interview APIs

| Endpoint | Purpose |
|----------|---------|
| `GET/POST /api/projects/{projectId}/stakeholders/{profileId}/interview-series` | List or create stakeholder topic series |
| `GET/POST /api/interview-series/{seriesId}/rounds` | List or create immutable rounds |
| `GET /api/interview-rounds/{roundId}` | Read round status and guide/session metadata |
| `POST /api/interview-rounds/{roundId}/generate-guide` | Generate an independent guide document for a round |
| `POST /api/interview-rounds/{roundId}/sessions` | Start a session from the round guide |

The legacy `generate-interview-guide` endpoint remains as a compatibility adapter. It resolves a default series and an editable draft round rather than reusing or deleting a historical guide.

### Key Hooks

| Hook | Purpose |
|------|---------|
| `useRealtimeTranscription` | WebRTC connection to OpenAI Realtime API |
| `useInterviewSession` | Interview session lifecycle and current-session state |
| `useTranscriptProcessing` | Realtime partial/completed transcript handling |
| `useCardEventHandlers` | Card events, manual selection, and SSE coordination |
| `useSSEEvents` | SSE subscription for card state updates & analysis progress |
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
| `answer_evaluation_engine` | Realtime transcript segment → card state and criterion-evidence updates |
| `semantic_judge_service` | GPT-based coverage/sufficiency judgments |
| `brd_generation_service` | Post-interview BRD document assembly + AI rewrite |
| `interview_service` | Session lifecycle, utterance CRUD, card state management |
| `document_service` | Document CRUD, file management |
| `event_service` | Redis pub/sub → SSE event distribution |
| `realtime_service` | OpenAI Realtime ephemeral token generation |

### Multi-Interview Services

| Service | Responsibility |
|---------|---------------|
| `project_service` | Project CRUD, dashboard |
| `stakeholder_plan_service` | Dynamic interview suggestions, slot management |
| `role_filter_service` | Filter cards by stakeholder expertise |
| `interview_brief_service` | Pre-interview guide generation |
| `insight_memo_service` | Post-interview qualitative analysis extraction |
| `interview_round_aggregate_service` | One canonical cumulative memo, coverage snapshot, and evidence snapshot per round |
| `evidence_matrix_service` | Cross-interview requirement consolidation & deduplication |
| `brd_readiness_service` | Readiness scoring before BRD generation |
| `stakeholder_card_generator` | Interview guide generation per stakeholder |

### Supporting Services

| Service | Responsibility |
|---------|---------------|
| `answer_completion_scorer` | Answer completeness scoring |
| `billing_service` | Token/audio cost tracking per session and per document |
| `s3_service` | MinIO file upload/download |
| `prep_session_service` | Prep session lifecycle |
| `question_card_service` | Card CRUD and reordering |
| `question_rubric_service` | Question rubric management |
| `ai_question_generator` | Coverage rules, target roles, suggested followup |
| `section_service` | Document section management |
| `report_analytics_service` | Post-interview performance analytics |
| `report_export_service` | Report export formatting |
| `brd_pdf_export_service` | BRD to PDF conversion |
| `brd_generator_service` | BRD content generation logic |

## AI Model Usage

| Model | Use Case | Latency Profile |
|-------|----------|----------------|
| GPT-5.5 | High-context document/section analysis | High |
| GPT-4o | Uploaded-document theme and question-card generation | Medium |
| GPT-5.4-mini | Stakeholder planning, answer evaluation, semantic judging, memo/matrix analysis | Low |
| gpt-realtime-whisper | Live audio transcription via WebRTC | Real-time |
| text-embedding-3-large | Configured for future semantic recall; current card prefilter is keyword/ngram based | Reserved |

## Key Design Decisions

1. **Theme-based interview structure**: Documents are analyzed into themes (not just pages), enabling logical interview flow regardless of document structure.

2. **Two-stage answer evaluation**: Fast keyword/character-ngram prefilter narrows candidates before the GPT semantic judgment, reducing unnecessary model calls.

3. **WebRTC for transcription**: Audio goes directly from browser to OpenAI — backend never handles audio data, reducing latency and bandwidth.

4. **Card state machine**: `pending → listening → probably_sufficient → sufficient` provides granular progress tracking with interviewer activation as a gate.

5. **Coverage rules on cards**: Each question card has `semanticAnchors`, `expectedKeywords`, and `mustMentionElements` — enabling both AI and deterministic evaluation.

6. **Single Realtime transcript source**: `live_utterances` is used for the live UI, historical records, Insight Memo, and report generation. The browser does not create or upload a second recording.

7. **Project-level multi-interview architecture**: Projects contain stakeholder plans, evidence matrices, and readiness gates — enabling systematic requirements research across multiple interviews.

8. **BRD caching**: Generated BRD documents are persisted to avoid non-deterministic regeneration on repeated page visits.

9. **Project and round ownership**: Project is the research-level root. InterviewSeries and InterviewRound preserve repeated-interview history; each guide Document owns its themes and cards, while sessions retain their own transcripts and state.

10. **Round Aggregate invalidation**: Session or memo changes mark the round aggregate and project-level derivatives stale. Evidence Matrix, BRD Readiness, and project BRD only read the latest memo selected by each ready round aggregate.

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
│   │   ├── stores/              # Zustand state management
│   │   ├── types/               # TypeScript type definitions
│   │   └── utils/               # Utility functions
│   └── vite.config.ts
├── docs/                        # Documentation
│   ├── knowledge/               # AI model guides & feature docs
│   └── ...
├── insightguide.sh              # Primary launch/management script
└── docker-compose.yml           # Docker services configuration
```

## Infrastructure Dependencies

| Service | Default Port | Purpose |
|---------|-------------|---------|
| FastAPI | 8002 | Backend API server |
| Vite dev server | 5174 | Frontend dev server |
| PostgreSQL | 5432 | Primary database (with pgvector) |
| Redis | 6379 | Event pub/sub + Celery broker |
| MinIO | 9000 (API) / 9001 (Console) | S3-compatible object storage |
| OpenAI API | — | AI inference (external) |
