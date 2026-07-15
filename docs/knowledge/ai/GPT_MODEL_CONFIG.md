# GPT Model Configuration

**Last Updated**: 2026-07-15
**Status**: Current configuration guide. Historical GPT-4o/Whisper notes remain in archived reports only.

## Current Model Selection

| Use Case | Model / Service | Configuration Source |
| --- | --- | --- |
| High-context document/section analysis | `gpt-5.5` | `DOCUMENT_ANALYSIS_MODEL` / `backend/app/services/openai_service.py` |
| Uploaded-document theme and Question Card generation | `gpt-4o` | `backend/app/services/openai_service.py` |
| Stakeholder-specific round guide generation | `gpt-5.4-mini` | `backend/app/services/stakeholder_card_generator.py` |
| Semantic judgment and Topic Card completion | `gpt-5.4-mini` | `SEMANTIC_UNDERSTANDING_MODEL` |
| Answer evaluation and card coverage | `gpt-5.4-mini` | `SEMANTIC_UNDERSTANDING_MODEL` |
| Insight Memo and Evidence Matrix analysis | `gpt-5.4-mini` | `backend/app/services/insight_memo_service.py`, `evidence_matrix_service.py` |
| Realtime transcription | `gpt-realtime-whisper` via WebRTC | `REALTIME_TRANSCRIPTION_MODEL` / `backend/app/services/realtime_service.py` |
| Embeddings | `text-embedding-3-large` is configured but not called by the current card-matching path | `EMBEDDING_MODEL` |

The effective runtime values should always be verified from:

```bash
backend/.env
backend/app/core/config.py
```

## Recommended Local `.env`

```bash
OPENAI_API_KEY=sk-...
DOCUMENT_ANALYSIS_MODEL=gpt-5.5
SEMANTIC_UNDERSTANDING_MODEL=gpt-5.4-mini
EMBEDDING_MODEL=text-embedding-3-large
```

Do not keep production credentials in the root `.env`; local service startup uses `backend/.env`.

## Why This Split

- `gpt-5.5` is the configurable high-context document-analysis model.
- `gpt-4o` currently generates themes and cards for an uploaded source document.
- `gpt-5.4-mini` handles stakeholder-specific planning, live evaluation, memo extraction, and matrix consolidation where latency and cost matter.
- Realtime transcription stays on the OpenAI Realtime/WebRTC path rather than a backup HTTP audio transcription flow.
- The application stores only completed Realtime transcript segments; it does not run speaker classification or Q/A reconstruction.
- Current candidate recall uses keyword and character-ngram scoring. `EMBEDDING_MODEL` is retained for a future semantic-recall implementation.

## Verification

Run these checks after changing model configuration:

```bash
cd backend
source venv/bin/activate
pytest tests/ -x --tb=short
mypy app/ --ignore-missing-imports
```

For frontend:

```bash
cd frontend
npx tsc --noEmit
npm run build
```

## Related Documentation

- [GPT-5.5 model guide](GPT-5.5-MODEL-GUIDE.md)
- [GPT-5.4-mini notes](GPT-5.4-MINI.md)
- [Architecture](../../ARCHITECTURE.md)
