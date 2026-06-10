# GPT Model Configuration

**Last Updated**: 2026-06-02
**Status**: Current configuration guide. Historical GPT-4o/Whisper notes remain in archived reports only.

## Current Model Selection

| Use Case | Model / Service | Configuration Source |
| --- | --- | --- |
| Slide analysis and Topic Card generation | `gpt-5.5` | `OPENAI_ANALYSIS_MODEL` / `backend/app/services/openai_service.py` |
| Topic Card metadata and generation helpers | `gpt-5.5` aligned generation path | `backend/app/services/openai_service.py`, `backend/app/services/ai_card_generator.py` |
| Semantic judgment and Topic Card completion | `gpt-5.4-mini` | `SEMANTIC_UNDERSTANDING_MODEL` |
| Script Plan progression | `gpt-5.4-mini` | `SEMANTIC_UNDERSTANDING_MODEL` |
| Bullet point cleanup and child-point extraction | `gpt-5.4-mini` | `SEMANTIC_UNDERSTANDING_MODEL` |
| Realtime transcription | OpenAI Realtime transcription via WebRTC | `backend/app/services/realtime_service.py` and frontend realtime hooks |
| Embeddings | `text-embedding-3-large` | `EMBEDDING_MODEL` |

The effective runtime values should always be verified from:

```bash
backend/.env
backend/app/core/config.py
```

## Recommended Local `.env`

```bash
OPENAI_API_KEY=sk-...
OPENAI_ANALYSIS_MODEL=gpt-5.5
SEMANTIC_UNDERSTANDING_MODEL=gpt-5.4-mini
EMBEDDING_MODEL=text-embedding-3-large
```

Do not keep production credentials in the root `.env`; local service startup uses `backend/.env`.

## Why This Split

- `gpt-5.5` is used for high-context generation tasks where quality matters more than latency.
- `gpt-5.4-mini` is used for live presenter checks where response time and cost are more important.
- Realtime transcription stays on the OpenAI Realtime/WebRTC path rather than a backup HTTP audio transcription flow.
- Embeddings are used for candidate recall before semantic judgment.

## Verification

Run these checks after changing model configuration:

```bash
cd backend
DEBUG=false venv/bin/python -m pytest tests/test_milestone_2.py tests/test_topic_matching_completion.py tests/test_script_plan_advance.py -q
DEBUG=false venv/bin/python -m compileall -q app tests
```

For frontend presenter behavior:

```bash
cd frontend
npm run lint
npm run build
```

## Related Documentation

- [GPT-5.5 model guide](GPT-5.5-MODEL-GUIDE.md)
- [GPT-5.4-mini notes](GPT-5.4-MINI.md)
- [Project status](../../reports/PROJECT_STATUS.md)
- [Architecture](../../architecture/SlideCue_開發架構書.md)
