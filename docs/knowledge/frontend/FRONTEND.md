# SlideCue Frontend

This file was moved from `frontend/README.md` into `docs/guides/` so project documentation stays centralized under `docs/`.

React + TypeScript + Vite frontend for SlideCue, an AI presentation copilot that helps speakers prepare, rehearse, present, and review coverage in real time.

## Tech Stack

- **Framework**: React 18
- **Language**: TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **Router**: React Router v6
- **HTTP Client**: Axios
- **State Management**: Zustand
- **Realtime**: Server-Sent Events and OpenAI Realtime transcription via WebRTC
- **Charts**: Recharts
- **Text Utilities**: OpenCC for Simplified-to-Traditional Chinese conversion

## Getting Started

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Type check
npm run type-check

# Lint
npm run lint

# Preview production build
npm run preview
```

The local frontend usually runs at:

```text
http://localhost:5173
```

## Environment

Create `frontend/.env` for local development.

```bash
VITE_API_BASE_URL=http://localhost:8001
VITE_WS_BASE_URL=ws://localhost:8001
```

`frontend/.env` is ignored by Git and should not be committed.

## Routes

- `/` - Upload a deck and start analysis
- `/sessions` - View and manage presentation sessions
- `/prep-sessions` - View and manage prep sessions and nested presentation sessions
- `/editor/:deckId` - Review slides and edit topic cards
- `/presenter/:deckId` - Start presenter mode

## Current Feature Status

### Upload And Analysis

- Upload supports PowerPoint and PDF files.
- The home page is upload-first and no longer includes marketing hero copy.
- The editor waits for backend processing status before loading slide data.
- Deck analysis progress is updated through SSE.

### Editor Mode

- Slide preview and topic card editing are implemented.
- Topic cards can be fetched, edited, sorted by slide/order, and refreshed as analysis events arrive.
- Coverage rules and card metadata are aligned with backend topic card models.
- Topic cards display up to three parent points; hidden `subpoints` can be required for completion.

### Presenter Mode

- Presentation sessions are created from ready prep sessions.
- Realtime transcription is implemented through `useRealtimeTranscription`.
- Transcript completion saves utterances to the backend.
- Partial transcript matching starts while speech is still streaming.
- Topic card state updates arrive through SSE.
- Topic card status updates are independent from Smart Prompt cursor advancement.
- Script Plan based prompting is the active suggested-script flow.
- Suggested prompts display two lines: current sentence and next sentence.
- A manual `下一句` button advances the prompt cursor without changing topic card status.
- Presenter entry is blocked by a preparation overlay until the microphone and suggested prompts are ready.
- Completion state is explicit: the prompt panel shows `建議逐字稿已完成`.

### Reports

- Session report view is implemented after a presentation ends.
- Coverage charts, topic analysis, timing, and recommendations are displayed.
- JSON and PDF export actions are available.

## Project Structure

```text
src/
├── api/
│   ├── client.ts
│   ├── decks.ts
│   ├── prepSessions.ts
│   ├── presentation.ts
│   ├── realtime.ts
│   ├── scriptPlan.ts
│   ├── sessions.ts
│   └── topicCards.ts
├── components/
│   ├── common/
│   ├── EditorMode/
│   ├── PresenterMode/
│   ├── SessionReport/
│   └── sessions/
├── hooks/
│   ├── useDeckEvents.ts
│   ├── usePrepSessionEvents.ts
│   ├── usePresentationSession.ts
│   ├── useRealtimeTranscription.ts
│   ├── useResponsiveLayout.ts
│   ├── useSSEEvents.ts
│   └── useScriptPlan.ts
├── routes/
│   ├── DeckUploadPage.tsx
│   ├── EditorPage.tsx
│   ├── PrepSessionListPage.tsx
│   ├── PresenterPage.tsx
│   └── SessionListPage.tsx
├── stores/
├── types/
├── utils/
├── App.tsx
├── main.tsx
└── index.css
```

## Milestones

| Milestone | Status | Frontend Scope |
| --- | --- | --- |
| M1 - Deck Upload | Complete | Upload page, deck API client, basic navigation to editor. |
| M2 - Slide Analysis And Topic Cards | Complete | Editor mode, slide preview, topic card editor, analysis SSE updates. |
| M3 - Session And Prep Session Management | Complete | Session list, prep session list, filters, sorting, deletion flows, global SSE updates. |
| M4 - Realtime Presenter Mode | Complete | Presenter layout, slide viewer, realtime transcription hook, transcript display, topic card live updates. |
| M5 - Smart Prompt / Script Plan | Complete Core | Two-line prompt display, automatic cursor progression, manual `下一句`, completion UI, and card/script dependency separation. Ongoing tuning for ASR errors and progression thresholds. |
| M6 - Responsive Presenter UX | Complete Core | Dynamic presenter layout, larger prompt area, preparation overlay, microphone/script readiness gating. Needs more viewport and live-session QA. |
| M7 - Session Report | Complete Core | Enhanced report page, charts, metrics, timeline, JSON/PDF export. Needs final browser QA and copy polish. |

## Known Gaps

- Presenter mode still needs more real speaking tests, especially for final-sentence completion and ASR wording drift.
- Some UI copy is still mixed Chinese/English.
- Vite build currently warns that the main bundle is larger than 500 kB.
- This document describes the current frontend state, but source-of-truth API contracts still live in the backend schemas and route implementations.

## Verification

Current expected frontend verification:

```bash
npm run lint
npm run build
```

For presenter-mode work, also verify against a running backend at `http://localhost:8001`.
The latest health check passed both commands on 2026-06-02.
