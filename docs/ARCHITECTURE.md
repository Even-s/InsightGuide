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
│  │  │  ├─ Themes     │  │  ├─ Embedding Service       │    │    │
│  │  │  ├─ Cards      │  │  ├─ Scoring Service         │    │    │
│  │  │  └─ Coverage   │  │  └─ Hallucination Filter    │    │    │
│  │  └────────────────┘  └─────────────────────────────┘    │    │
│  │  ┌────────────────┐  ┌─────────────────────────────┐    │    │
│  │  │ Post-Interview │  │ Project-Level Analysis      │    │    │
│  │  │  ├─ Insight    │  │  ├─ Stakeholder Plan        │    │    │
│  │  │  │   Memo      │  │  ├─ Evidence Matrix         │    │    │
│  │  │  ├─ Q/A Recon  │  │  ├─ BRD Readiness          │    │    │
│  │  │  └─ BRD Gen    │  │  └─ Role Filter            │    │    │
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
 │    │         ├── CardCoverageEvaluation (1:N, basis_type: live|final)
 │    │         └── CardCriterionEvidence (1:N)
 │    ├── PrepSession (1:1) — preparation container
 │    │    └── InterviewSession (1:N) — actual interview runs
 │    │         ├── InterviewCardState (1:N)
 │    │         ├── LiveUtterance (1:N) — real-time provisional transcripts
 │    │         ├── FinalUtterance (1:N) — diarized official transcripts
 │    │         ├── UtteranceAlignment (1:N) — live↔final mapping
 │    │         ├── TranscriptRevision (1:N) — transcript versions
 │    │         ├── QuestionInstance + QuestionAnswer (Q/A reconstruction)
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

### 5. Post-Interview Pipeline

```
Interview ends
  → Diarization (gpt-4o-transcribe) → FinalUtterances
  → Alignment (live_utterances ↔ final_utterances)
  → Q/A Reconstruction (question_instances + question_answers)
  → Final Card Coverage Re-evaluation (basis_type='final')
  → Insight Memo Generation
    → Pain points, requirement candidates, constraints, unresolved questions
  → Stakeholder Plan Update (dynamic interview suggestions)
  → Evidence Matrix Update (if project-level)
  → BRD Generation (from final evidence only)
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
| `/` | DocumentUploadPage | Upload requirement documents |
| `/projects` | ProjectSessionsPage | Project-centric session management |
| `/projects/:projectId` | ProjectDetailPage | Stakeholder plan, guides, readiness |
| `/projects/:projectId/evidence-matrix` | EvidenceMatrixPage | Cross-stakeholder requirement validation |
| `/projects/:projectId/readiness` | BRDReadinessPage | BRD generation feasibility check |
| `/prep-sessions` | PrepSessionListPage | Manage all prep sessions (admin) |
| `/editor/:deckId` | EditorPage | Review/edit themes & question cards |
| `/interview/:deckId` | PresenterPage | Live interview with transcription |
| `/interview/session/:sessionId` | PresenterPage | Resume interview by session |
| `/interview/:deckId/report/:sessionId` | InterviewReportPage | Post-interview analytics |
| `/interview/:sessionId/brd` | BRDGenerationPage | Structured BRD editor |
| `/sessions/:sessionId/insight-memo` | InsightMemoPage | Post-interview qualitative analysis |
| `/sessions/:sessionId/log` | SessionLogPage | Event timeline |

### Key Hooks

| Hook | Purpose |
|------|---------|
| `useRealtimeTranscription` | WebRTC connection to OpenAI Realtime API |
| `usePresentationSession` | Interview session state, theme navigation |
| `useSSEEvents` | SSE subscription for card state updates & analysis progress |
| `useResponsiveLayout` | Adaptive layout for interview mode |
| `useMediaRecorder` | Audio recording during interview for post-diarization |

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
| `evidence_matrix_service` | Cross-interview requirement consolidation & deduplication |
| `brd_readiness_service` | Readiness scoring before BRD generation |
| `brd_readiness_evaluator` | Detailed readiness evaluation logic |
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
| `diarize_service` | Post-interview speaker diarization |
| `alignment_service` | Live↔final utterance mapping |
| `qa_reconstruction_service` | Q/A pair extraction from transcript |
| `section_service` | Document section management |
| `report_analytics_service` | Post-interview performance analytics |
| `report_export_service` | Report export formatting |
| `brd_pdf_export_service` | BRD to PDF conversion |
| `brd_generator_service` | BRD content generation logic |

## AI Model Usage

| Model | Use Case | Latency Profile |
|-------|----------|----------------|
| GPT-5.5 | Document section analysis (highest quality) | High (~10s) |
| GPT-4o | Interview theme + question card generation | Medium (~5s) |
| GPT-5.4-mini | Speaker classification, answer evaluation, semantic judging | Low (~1s) |
| gpt-4o-transcribe | Post-interview diarization | Medium (~5-15s) |
| gpt-realtime-whisper | Live audio transcription via WebRTC | Real-time |
| text-embedding-3-large | Semantic similarity for card matching | Low (~200ms) |

## Key Design Decisions

1. **Theme-based interview structure**: Documents are analyzed into themes (not just pages), enabling logical interview flow regardless of document structure.

2. **Two-stage answer evaluation**: Fast embedding recall + deep AI judgment prevents unnecessary GPT calls while maintaining accuracy.

3. **WebRTC for transcription**: Audio goes directly from browser to OpenAI — backend never handles audio data, reducing latency and bandwidth.

4. **Card state machine**: `pending → listening → probably_sufficient → sufficient` provides granular progress tracking with interviewer activation as a gate.

5. **Coverage rules on cards**: Each question card has `semanticAnchors`, `expectedKeywords`, and `mustMentionElements` — enabling both AI and deterministic evaluation.

6. **Live/Final transcript separation**: `live_utterances` for real-time provisional UI, `final_utterances` for official reports. Prevents provisional data from contaminating formal outputs.

7. **Project-level multi-interview architecture**: Projects contain stakeholder plans, evidence matrices, and readiness gates — enabling systematic requirements research across multiple interviews.

8. **BRD caching**: Generated BRD documents are persisted to avoid non-deterministic regeneration on repeated page visits.

9. **Cascade deletion via Document**: Document is the aggregate root. Deleting it cascades to all related data (themes, cards, sessions, utterances, BRDs, billing events).

## Directory Structure

```
InsightGuide/
├── backend/
│   ├── app/
│   │   ├── api/routes/          # FastAPI route handlers (19 files)
│   │   ├── core/                # Config, security, logging
│   │   ├── db/                  # SQLAlchemy session, Alembic migrations
│   │   ├── models/              # SQLAlchemy ORM models (25 files)
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── services/            # Business logic layer (32 files)
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
│   │   ├── hooks/               # Custom React hooks (13 files)
│   │   ├── routes/              # Page-level components (13 files)
│   │   ├── stores/              # Zustand state management
│   │   ├── types/               # TypeScript type definitions
│   │   └── utils/               # Utility functions
│   └── vite.config.ts
├── docs/                        # Documentation
│   ├── knowledge/               # AI model guides & feature docs
│   └── ...
├── scripts/
│   └── integration_tests/       # End-to-end test scripts
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
