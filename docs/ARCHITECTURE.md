# InsightGuide Architecture

## Overview

InsightGuide is a modular monolith with a separate Celery worker. It supports the complete requirements-interview lifecycle: preparing an interview guide, conducting a Realtime interview, consolidating evidence across rounds, checking BRD readiness, and generating a Markdown BRD.

The browser, FastAPI application, Celery worker, PostgreSQL, Redis, MinIO, and OpenAI API are the main runtime components. Local development uses a hybrid topology; the EC2 prototype packages the same components into a single-host Docker Compose deployment.

## System Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, TypeScript, Vite 5, Tailwind CSS, React Router |
| Frontend state | React hooks and component state; there is no Zustand store layer |
| Backend | Python 3.11, FastAPI, SQLAlchemy, Pydantic |
| Database | PostgreSQL 16 with pgvector |
| Events / queue | Redis Pub/Sub for SSE; separate Redis databases for Celery broker and result backend |
| Object storage | MinIO (S3-compatible) |
| Background worker | Celery; currently only the document-analysis task is registered |
| AI | OpenAI Chat Completions and Realtime transcription over WebRTC |

## Runtime Topology

### Local development (hybrid)

`docker-compose.yml` starts infrastructure only. `./insightguide.sh` runs the application processes directly on the host after applying database migrations.

```text
Browser
  ├── UI assets ─────> Vite :5174
  ├── REST/SSE ─────> FastAPI :8002
  └── WebRTC audio ─> OpenAI Realtime API

Host processes
  ├── FastAPI :8002
  ├── Celery worker (solo pool)
  └── Vite :5174

Docker infrastructure
  ├── PostgreSQL + pgvector :5432
  ├── Redis :6379
  └── MinIO API :9000 / Console :9001

FastAPI / Celery ──> PostgreSQL, Redis, MinIO, OpenAI API
```

### EC2 prototype (single host)

`deploy/ec2/docker-compose.yml` runs all services on one EC2 host. Only Caddy's HTTP/HTTPS ports are public by default; MinIO's API is bound to loopback unless overridden.

```text
Internet
  │
  ▼
Caddy :80/:443
  ├── application host
  │    ├── /api/*, /health, /docs*, /redoc*, /openapi.json
  │    │       └── reverse_proxy ──> FastAPI :8002
  │    └── all other paths ───────> React static files with SPA fallback
  └── files host ─────────────────> MinIO :9000

Docker Compose network
  ├── backend (FastAPI, default 2 workers)
  ├── worker (Celery, default concurrency 2)
  ├── migrate (on-demand bootstrap / migration tool)
  ├── PostgreSQL + pgvector
  ├── password-protected Redis
  └── MinIO + one-shot bucket initializer
```

Caddy keeps upstream reads open (`read_timeout 0` and `flush_interval -1`) so SSE responses are streamed instead of buffered. TLS is managed by Caddy for the configured application and file host names.

## Application Boundaries

### Frontend

`frontend/src/App.tsx` lazy-loads route components behind React Router. State is kept in route components and custom hooks; API clients live under `frontend/src/api`. There is no `stores` directory or Zustand dependency.

| Route | Component | Purpose |
|-------|-----------|---------|
| `/` | `HomePage` | Quick Demo templates plus project creation and management entry points |
| `/projects/new` | `DocumentUploadPage` | Create a project and upload source material |
| `/projects` | `ProjectSessionsPage` | Project-centric session management |
| `/projects/:projectId` | `ProjectDetailPage` | Project dashboard, plan, guides, and readiness |
| `/projects/:projectId/stakeholders` | `StakeholdersPage` | Manage stakeholder people and role assignments |
| `/projects/:projectId/evidence-matrix` | `EvidenceMatrixPage` | Cross-interview evidence consolidation |
| `/projects/:projectId/readiness` | `BRDReadinessPage` | Readiness check and Markdown BRD generation |
| `/prep-sessions` | `PrepSessionListPage` | Preparation-session administration |
| `/editor/:documentId` | `EditorPage` | Review and edit themes and cards |
| `/interview/:documentId` | `PresenterPage` | Start an interview from a guide document |
| `/interview/session/:sessionId` | `PresenterPage` | Resume an interview session |
| `/sessions/:sessionId/insight-memo` | `InsightMemoPage` | Post-interview memo |
| `/sessions/:sessionId/log` | `SessionLogPage` | Transcript and event timeline |

Key hooks include `useRealtimeTranscription`, `useInterviewSession`, `useTranscriptProcessing`, `useCardEventHandlers`, `useSSEEvents`, `useProjectData`, `useSlotManagement`, and `useResponsiveLayout`.

### FastAPI modular monolith

`backend/app/main.py` mounts routers for documents, question cards, interview sessions, authentication, events, Realtime, prep sessions, projects, insight memos, interview rounds, and evidence matrices. The interview-session router aggregates lifecycle, utterance, card-control, and output subrouters.

The service layer contains the business logic:

| Area | Main services |
|------|---------------|
| Document / card preparation | `document_service`, `openai_service`, `question_card_service`, `question_rubric_service`, `ai_question_generator` |
| Live interview | `interview_service`, `answer_evaluation_engine`, `semantic_judge_service`, `event_service`, `realtime_service` |
| Multi-interview planning | `project_service`, `stakeholder_plan_service`, `role_filter_service`, `stakeholder_card_generator`, `interview_brief_service` |
| Post-interview derivation | `insight_memo_service`, `interview_round_aggregate_service`, `evidence_matrix_service`, `brd_readiness_service`, `brd_generation_service` |
| Infrastructure / accounting | `s3_service`, `billing_service`, `prep_session_service` |
| Ready-to-run demos | `demo_session_service` |

### Celery worker scope

`app.workers.celery_app` registers only `app.workers.document_analysis_worker`. Its production task is `analyze_document`, which downloads the source from MinIO, parses guide chunks, calls OpenAI to create themes and cards, persists them, and publishes progress through Redis.

Realtime utterance evaluation is not a Celery job. The utterance endpoint stores each completed transcript segment, then uses a FastAPI background task plus one in-process debounce timer per session before running `answer_evaluation_engine`. This means pending evaluation timers are local to a FastAPI process and are not a durable distributed queue.

## Data Model

The clean-v2 model is project- and round-centric. The important ownership paths are:

```text
User
├── Project
│   ├── StakeholderSlot                 recommended role
│   ├── StakeholderProfile              actual person
│   │   └── StakeholderProfileSlot      many-to-many person/role assignment
│   ├── InterviewSeries                 person + recurring topic
│   │   └── InterviewRound              immutable guide version / round
│   │       ├── InterviewRoundSlot      targeted role assignment
│   │       ├── Document                generated guide
│   │       ├── InterviewSession        one or more visits
│   │       ├── InterviewInsightMemo    memo per completed visit
│   │       └── InterviewRoundAggregate canonical latest memo and snapshots
│   ├── RequirementEvidenceMatrix       refresh metadata + Markdown, one per project
│   └── BRDReadinessReport              readiness history
└── Document
    ├── InterviewTheme
    │   └── QuestionCard
    │       └── QuestionCardSlot        card/role targeting
    ├── PrepSession
    │   └── InterviewSession
    │       ├── LiveUtterance           canonical Realtime transcript
    │       ├── InterviewCardState
    │       ├── CardCoverageEvaluation
    │       ├── CardCriterionEvidence
    │       │   └── CardEvidenceSlot    evidence/role attribution
    │       ├── InterviewBrief
    │       └── AIUsageEvent
    └── AIUsageEvent                    document-level usage
```

Requirement rows are derived from ready `InterviewRoundAggregate` snapshots at read time. They are not stored in a separate `EvidenceMatrixEntry` table. This keeps the round aggregate as the source of truth for project-level evidence.

`Project` also carries explicit lifecycle metadata: `mode` (`formal` or `demo`), `is_ephemeral`, `expires_at`, and `template_id`. Formal project listings exclude Demo projects. Each Demo request creates a separate project aggregate, so transcripts and card state are never shared between visitors.

## Core Workflows

### 0. Quick Demo interview

```text
HomePage selects one public template
  └── POST /api/demo-sessions
      └── one database transaction
          ├── create ephemeral Project + default StakeholderSlot/Profile
          ├── create InterviewSeries/Round + analyzed Document + ready PrepSession
          ├── copy template InterviewThemes/Cards with precompiled rubrics
          ├── create idle InterviewSession + card states
          └── return /interview/session/{sessionId}
              └── existing PresenterPage and Realtime workflow
```

The built-in templates are 現況流程探索, 痛點與需求探索, and 新系統需求確認. This path does not upload a source file, enqueue Celery, or call OpenAI to generate the guide. Demo projects expire after 24 hours; expired Demo aggregates are opportunistically deleted when another Demo is created.

### 1. Document upload and analysis

```text
Upload source
  └── FastAPI validates extension and writes the object to MinIO
      └── Celery analyze_document
          ├── read source as UTF-8 and split Markdown-style headings into chunks
          ├── generate_interview_themes                 [hard-coded gpt-4o]
          ├── generate_theme_question_cards per theme   [hard-coded gpt-4o]
          ├── save InterviewTheme and QuestionCard rows
          └── publish analysis progress/completion events through Redis
```

The upload API currently accepts `.pdf`, `.docx`, `.doc`, `.md`, and `.txt`, but the worker only decodes the downloaded object as UTF-8 text. Binary PDF/DOC/DOCX extraction is not implemented, so those accepted formats are not yet reliably analyzable unless they contain compatible text bytes. Markdown and plain text are the dependable analysis inputs today.

### 2. Repeated interviews

```text
Project + StakeholderProfile
  └── InterviewSeries
      └── InterviewRound (objective, mode, sources, focus, target slots)
          ├── generate an independent Document + PrepSession + themes/cards
          ├── freeze the guide when a session is created
          └── create/resume one or more InterviewSessions
```

Historical rounds retain their own guide, cards, transcript, state, and memo. New rounds use the `InterviewSeries` / `InterviewRound` APIs; retired deck/section compatibility contracts are not part of the clean-v2 API.

### 3. Realtime interview and answer evaluation

```text
Browser requests POST /api/realtime/transcription-session
  └── FastAPI exchanges the server API key for an ephemeral client secret
      └── Browser opens WebRTC directly to OpenAI Realtime
          ├── audio never passes through FastAPI
          ├── transcript deltas stay in the browser
          └── completed utterance POSTed to /api/interview-sessions/{id}/utterances
              ├── persist LiveUtterance
              ├── debounce and evaluate in the FastAPI process
              ├── suggest/score cards with GPT-5.4-mini where needed
              └── publish card/evidence updates through Redis → SSE → browser
```

`LiveUtterance` is the canonical transcript. The system does not upload a second recording or run a separate diarization/transcription pipeline.

The card state flow is `pending → listening → probably_sufficient → sufficient`, with `at_risk` available during evaluation. AI can suggest and mark `probably_sufficient`; a human action is the final gate to `sufficient`.

### 4. Post-interview and project outputs

```text
End session
  └── create cumulative InterviewInsightMemo
      └── rebuild InterviewRoundAggregate
          ├── coverage snapshot
          ├── evidence snapshot
          └── latest cumulative memo

Ready round aggregates
  ├── Evidence Matrix refresh/read
  ├── BRD Readiness report
  └── BRD generation → cached Markdown content
```

Session or memo changes invalidate the round aggregate and project-level derivatives. Evidence Matrix, BRD Readiness, and project BRD generation read ready aggregates only. The current BRD API returns Markdown; PDF export is not implemented.

## AI Model Usage

| Configuration / model | Actual use |
|-----------------------|------------|
| `gpt-4o` | Hard-coded for the two initial uploaded-document phases: theme generation and per-theme question-card generation |
| `DOCUMENT_ANALYSIS_MODEL` (default `gpt-5.5`) | Used by `openai_service.generate_card_metadata`; it is not the model used by the initial theme/card worker phases |
| `SEMANTIC_UNDERSTANDING_MODEL` (default `gpt-5.4-mini`) | Semantic judgment and rubric-related calls; several planning, memo, matrix, guide, and evaluation services also explicitly select `gpt-5.4-mini` |
| `REALTIME_TRANSCRIPTION_MODEL` (default `gpt-realtime-whisper`) | OpenAI Realtime transcription session configuration |
| `gpt-4o-transcribe` | Voice-to-project/stakeholder field transcription endpoints in `projects.py` |
| `EMBEDDING_MODEL` (default `text-embedding-3-large`) | Reserved configuration; the current card candidate prefilter uses keywords / character n-grams, not vector retrieval |

## Communication Paths

- **REST:** browser to FastAPI for CRUD, lifecycle actions, completed utterances, and derived outputs.
- **SSE:** FastAPI streams Redis Pub/Sub events for analysis progress and live card/evidence changes.
- **WebRTC:** browser sends microphone audio directly to OpenAI and receives transcription events over the data channel.
- **Celery:** FastAPI dispatches durable document-analysis work through the Redis broker; results use a separate Redis database.
- **S3 API:** FastAPI and Celery use MinIO for source objects and presigned downloads.

## Authentication and Security Status

Authentication is currently a development stub, not a production multi-user authorization boundary:

- registration returns a fixed development identity;
- login accepts any submitted credentials and issues a JWT for `dev-user`;
- `/api/auth/me` decodes no application identity and returns the fixed development user;
- application routes are not consistently protected by `get_current_user`;
- most application records use the seeded `user_default` database owner.

Production use requires real credential verification, route authorization, tenant ownership checks, secret rotation, and a non-default `SECRET_KEY`. EC2 narrows CORS to `APP_ORIGIN`, protects Redis with a password, keeps MinIO private, and exposes application/file traffic through Caddy, but those controls do not replace application authentication.

## Database Migration and Clean-v2 Gate

The two managed environments use different migration entry points:

- **Local launcher:** `bin/restart-all.sh` calls `run_migrations`, which runs `alembic upgrade head` before FastAPI starts. It does not call the clean-schema smoke check.
- **EC2 deploy / restore:** the Compose `migrate` service runs `python -m scripts.bootstrap_database` before the application is replaced or restored.

The EC2 bootstrap path is fail-closed:

1. An empty database gets the current SQLAlchemy schema, the `vector` extension, an Alembic head stamp, and the default user.
2. An Alembic-managed database is upgraded to head.
3. A non-empty application database without `alembic_version` is rejected; the script will not guess or stamp legacy state.
4. `smoke_clean_baseline_schema.py` must pass. It requires clean-v2 tables and columns and fails if retired deck/section/transcript compatibility tables or columns remain.

Therefore the enforced clean-v2 gate applies to the EC2 deploy/restore workflow. Local launches apply Alembic migrations, but developers must run the smoke check separately when they need to prove the absence of legacy compatibility shapes.

## Directory Structure

```text
InsightGuide/
├── backend/
│   ├── app/
│   │   ├── api/routes/       FastAPI routers and interview subrouters
│   │   ├── core/             settings, logging, security helpers
│   │   ├── db/               SQLAlchemy session and Alembic migrations
│   │   ├── models/           SQLAlchemy ORM models
│   │   ├── schemas/          Pydantic request/response models
│   │   ├── services/         business logic
│   │   └── workers/          Celery app and document analysis task
│   ├── scripts/              database bootstrap and schema checks
│   └── tests/                Pytest suite
├── frontend/
│   └── src/
│       ├── api/              Axios API clients
│       ├── components/       shared and feature UI components
│       ├── hooks/            local/session/realtime state orchestration
│       ├── routes/           lazy-loaded page components
│       ├── types/            TypeScript types
│       └── utils/            formatting and language helpers
├── deploy/ec2/               single-host Compose, Caddy, deploy/restore scripts
├── docs/                     architecture, operations, plans, and model notes
├── docker-compose.yml        local infrastructure only
└── insightguide.sh           local application control center
```

## Default Local Ports

| Service | Port | Purpose |
|---------|------|---------|
| Vite | 5174 | Frontend development server |
| FastAPI | 8002 | Backend API and SSE |
| PostgreSQL | 5432 | Primary database |
| Redis | 6379 | Pub/Sub and Celery transport |
| MinIO | 9000 / 9001 | S3 API / local console |
| OpenAI API | external | Chat and Realtime inference |
