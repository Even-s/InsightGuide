# Codebase Health Audit Report

**Date**: 2026-06-25  
**Scope**: Full backend + frontend + tests + config  
**Method**: Automated tooling + manual inspection across 209 source files

---

## A. Executive Summary

1. **Backend tests pass**: 332 tests, 47% coverage, all green.
2. **Frontend is clean**: lint (0 errors), TypeScript (0 errors), build (0 warnings), 29 Vitest tests pass.
3. **One P0 runtime bug**: `utterances.py:160` calls a non-existent method (`_is_question_like`), crashing the candidate card suggestion flow during live interviews.
4. **SSE event contract mismatch**: Backend emits events (`ANSWER_BUFFER_REPLAYED`, `CARD_UNDO_COMPLETED`) that frontend ignores; frontend listens for events (`CARD_PROBABLY_COVERED`, `MATCHING_ERROR`) that backend never emits.
5. **SessionStatus type mismatch**: Backend returns `section_transitioning`, frontend expects `transitioning`.
6. **Memory leak risk**: `event_service.py` `_queue_loops` dict is never cleaned on client disconnect.
7. **Document analysis worker is not idempotent**: Celery retries can create duplicate themes/cards.
8. **Dead code exists**: `PresenterMode/MarkdownOutput.tsx` is an unused duplicate; `presentationAPI` export is dead; deprecated type aliases unused.
9. **Diarize service** uses direct OpenAI client for Whisper API (by design — shared wrapper doesn't support audio). But billing is not tracked.
10. **Confusing naming**: `brd_generation_service.py` vs `brd_generator_service.py` serve different purposes but names are misleading.

---

## B. Top 10 Issues to Fix First

### 1. P0 — `_is_question_like` method does not exist
- **File**: `backend/app/api/routes/utterances.py:160`
- **Issue**: Calls `answer_evaluation_engine._is_question_like(transcript)` — this method doesn't exist on the class. The function is `is_question_like()` from `app.services.evaluation`.
- **Impact**: Crashes at runtime when user speaks a question-like utterance without an active card. Candidate card suggestions break.
- **Fix**: Import `is_question_like` from `app.services.evaluation` and call it directly.
- **Affects public API**: No schema change, but fixes broken SSE event emission.

### 2. P0 — SSE event name mismatch: `CARD_PROBABLY_COVERED`
- **File**: Frontend `useSSEEvents.ts` listens for `CARD_PROBABLY_COVERED`; backend never emits it.
- **Issue**: The evaluation engine sets cards to `probably_sufficient` status but the SSE event emitted is `CARD_LISTENING` (with confidence). Frontend never gets notified of "probably covered" state.
- **Impact**: Cards shown as "listening" in UI even when backend has marked them `probably_sufficient`.
- **Fix**: Backend should emit `CARD_PROBABLY_COVERED` when state is `probably_sufficient`, OR frontend should derive this from confidence in `CARD_LISTENING` events.
- **Affects public API**: Yes — new SSE event type or changed event semantics.

### 3. P1 — SessionStatus type mismatch
- **File**: Backend `schemas/interview.py:22` sends `section_transitioning`; frontend `types/interview.ts:13` expects `transitioning`.
- **Issue**: TypeScript won't catch this at runtime since it's a string union, but UI conditional logic checking `session.status === 'transitioning'` will never match.
- **Impact**: UI may not show correct state during theme transitions.
- **Fix**: Align naming — either backend sends `transitioning` or frontend expects `section_transitioning`.

### 4. P1 — Event service memory leak
- **File**: `backend/app/services/event_service.py:30`
- **Issue**: `_queue_loops` dict entries are only removed on explicit `unsubscribe()`. If clients disconnect without clean unsubscribe (network drop, browser close), entries accumulate.
- **Impact**: Long-running backend OOM after many sessions.
- **Fix**: Add cleanup in `publish()` when `queue.put_nowait` raises for a dead queue; remove from both `_connections` and `_queue_loops`.

### 5. P1 — Document analysis worker not idempotent
- **File**: `backend/app/workers/document_analysis_worker.py`
- **Issue**: On Celery retry after partial completion, themes/cards are created again (UUID-based IDs, no dedup). No guard against double-execution.
- **Impact**: Duplicate themes and cards in database after worker crash + retry.
- **Fix**: Check if themes already exist before creating; add idempotency key or DB unique constraint.

### 6. P1 — Diarize service billing not tracked
- **File**: `backend/app/services/diarize_service.py:27`
- **Issue**: Creates own `OpenAI()` client for Whisper API. Transcription costs (~$0.006/min) are never recorded in `ai_usage_events`.
- **Impact**: Billing dashboard undercounts. For a 30-min interview, ~$0.18 in Whisper costs go untracked.
- **Fix**: After `client.audio.transcriptions.create()`, manually call `billing_service.calculate_token_cost()` with audio seconds.

### 7. P1 — Frontend `MATCHING_ERROR` listener has no backend emitter
- **File**: Frontend `useSSEEvents.ts` listens for `MATCHING_ERROR`; backend never emits this event type.
- **Issue**: When partial transcript matching fails, the error is logged server-side but frontend never learns about it.
- **Impact**: UI `transcriptionError` state is never set from SSE for matching failures — only from direct API call failures.
- **Fix**: Add `MATCHING_ERROR` emission in the utterance matching error path, or remove dead frontend listener.

### 8. P1 — ThemeCardsList re-computes groupings on every render
- **File**: `frontend/src/components/PresenterMode/ThemeCardsList.tsx:16-29`
- **Issue**: `cardStateMap` and `groups` array are recomputed on every render (no `useMemo`). Parent re-renders on `activeCardId` changes trigger expensive O(n) regrouping.
- **Impact**: Visible lag on low-end devices with 30+ cards per theme.
- **Fix**: Wrap in `useMemo(() => ..., [cardStates, currentTheme.cards])`.

### 9. P1 — Backend emits `ANSWER_BUFFER_REPLAYED` / `CARD_UNDO_COMPLETED` but frontend ignores
- **File**: Backend `card_controls.py` emits these; frontend `useSSEEvents.ts` has no listeners.
- **Issue**: When buffered answers are replayed after user confirms a card, or a card completion is undone, the frontend doesn't update UI from SSE — only from the next card evaluation.
- **Impact**: UI may show stale card states until next utterance triggers re-evaluation.
- **Fix**: Add `onAnswerBufferReplayed` and `onCardUndoCompleted` handlers in `useSSEEvents`.

### 10. P2 — Dead file: `PresenterMode/MarkdownOutput.tsx`
- **File**: `frontend/src/components/PresenterMode/MarkdownOutput.tsx`
- **Issue**: Identical copy of `common/MarkdownOutput.tsx`, never imported anywhere.
- **Impact**: 211 lines of dead code in the bundle (though tree-shaken in prod).
- **Fix**: Delete the file.

---

## C. Safe Cleanup List

| # | File | Issue | Action |
|---|------|-------|--------|
| 1 | `frontend/src/components/PresenterMode/MarkdownOutput.tsx` | Identical duplicate, never imported | DELETE |
| 2 | `frontend/src/api/interview.ts:253` | `export const presentationAPI = interviewAPI` — never imported | DELETE line |
| 3 | `frontend/src/types/interview.ts:122-128` | Deprecated type aliases (`PresentationSession`, `Slide`, `PresentationCardState`) — unused | DELETE |
| 4 | `frontend/src/hooks/useCardEventHandlers.ts:56` | `const [, setCardsLoading] = useState(true)` — setter never used | Remove or use for loading UI |
| 5 | `backend/app/models/interview_session.py` | `interview_scope` JSON field — set but never read | Confirm unused, then remove |

---

## D. Do-Not-Touch List

| File | Reason |
|------|--------|
| `backend/app/services/brd_generation_service.py` | Used by InterviewReportPage — different from `brd_generator_service.py` |
| `backend/app/services/brd_generator_service.py` | Used by BRDGenerationPage — structured requirement extraction |
| `backend/app/services/diarize_service.py` (own OpenAI client) | Uses Whisper audio API which the shared wrapper doesn't support |
| `frontend/src/api/interview.ts` (snake_case → camelCase normalizers) | Backward-compatible field name fallbacks for old API versions |
| `backend/app/workers/session_report_worker.py` | Currently a stub — placeholder for future feature, not dead code |
| `backend/app/services/openai_service.py` (non-wrapper methods) | `generate_interview_themes` and `generate_theme_question_cards` use direct `self.client` — intentional for different prompt patterns |

---

## E. Suggested Fix Plan

### Fix Pass 1: P0 Bugs (30 min)

1. **Fix `utterances.py:160`**: Replace `answer_evaluation_engine._is_question_like(transcript)` with imported `is_question_like(transcript)`.
2. **Fix SSE `CARD_PROBABLY_COVERED`**: Either emit the event from backend when `probably_sufficient` state is reached, or map it in frontend from existing `CARD_LISTENING` events with confidence > threshold.

### Fix Pass 2: P1 Reliability (2-3 hours)

3. Fix `SessionStatus` type mismatch (frontend `transitioning` → `section_transitioning`).
4. Add cleanup for dead queues in `event_service.py` `publish()` method.
5. Add idempotency guard in `document_analysis_worker.py` (check for existing themes).
6. Add billing tracking for diarize Whisper calls.
7. Add `MATCHING_ERROR` SSE emission in backend or remove dead frontend listener.
8. Add `onAnswerBufferReplayed`/`onCardUndoCompleted` handlers to `useSSEEvents.ts`.

### Fix Pass 3: P2 Cleanup (1 hour)

9. Delete `PresenterMode/MarkdownOutput.tsx`.
10. Remove `presentationAPI` export and deprecated type aliases.
11. Remove unused `setCardsLoading` state.
12. Add `useMemo` to ThemeCardsList grouping logic.
13. Add null checks to unsafe `!` assertions in `InterviewReportPage`, `PrepSessionListPage`, `InsightMemoPage`.

### Fix Pass 4: Optional (future sessions)

14. Rename BRD services for clarity (`brd_generation_service` → `brd_report_service`?).
15. Add tests for `document_analysis_worker`, `event_service`, `openai_service`.
16. Implement `session_report_worker.py` (currently stub).
17. Add `useMemo`/`React.memo` to other heavy render paths.

---

## F. Automated Check Results

| Check | Result |
|-------|--------|
| `npm run lint` | PASS (0 errors, 0 warnings) |
| `npm run build` | PASS (no chunk warnings) |
| `pytest` (332 tests) | PASS (24 warnings — deprecation notices) |
| `black --check` | PASS (123 files unchanged) |
| `isort --check-only` | PASS |
| `mypy` | 395 errors in 43 files (SQLAlchemy Column type annotations — cosmetic, not runtime bugs) |

### mypy Summary
All 395 mypy errors are SQLAlchemy ORM type annotation issues (`Column[str]` vs `str` assignments). These are false positives from mypy not understanding SQLAlchemy's descriptor protocol. They do NOT indicate runtime bugs. Standard mitigation is adding `sqlalchemy-stubs` or `sqlalchemy[mypy]` plugin — optional improvement.

---

## G. Metrics

| Metric | Value |
|--------|-------|
| Total source files | 209 |
| Backend services | 32 |
| Backend routes | 14 |
| Backend models | 25 |
| Backend tests | 332 (47% coverage) |
| Frontend pages | 12 |
| Frontend hooks | 8 |
| Frontend tests | 29 |
| P0 issues | 2 |
| P1 issues | 7 |
| P2 issues | 5 |
| P3 issues | 4 |
