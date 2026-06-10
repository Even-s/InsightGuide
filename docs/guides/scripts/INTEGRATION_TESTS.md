# Integration Tests

This directory contains integration test scripts for testing SlideCue milestones end-to-end.

## Prerequisites

- Backend server running at `http://localhost:8001`
- All infrastructure services running (PostgreSQL, Redis, MinIO)
- OpenAI API key configured in `backend/.env`

## Available Tests

### Milestone 2: AI Slide Analysis + Topic Card Generation

```bash
python scripts/integration_tests/test_milestone2.py
```

Tests:
- PPTX upload
- PDF conversion and slide extraction
- AI-powered slide analysis
- Topic card generation with coverage rules

### Milestone 4: Realtime Transcription Integration

```bash
python scripts/integration_tests/test_milestone4.py
```

Tests:
- Ephemeral token generation for OpenAI Realtime API
- Presentation session creation and management
- Utterance creation
- Session status transitions

### Milestone 5: Topic Matching Engine

```bash
# Full test suite
python scripts/integration_tests/test_milestone5.py

# Simplified test (component-level)
python scripts/integration_tests/test_milestone5_simple.py
```

Tests:
- Candidate card recall using embeddings
- Configured semantic understanding model, currently `gpt-5.4-mini`
- Keyword and fact scoring
- Card status updates
- SSE event emission

### Bullet Point Generation

```bash
python scripts/integration_tests/test_bullet_points.py
```

Tests:
- Bullet point extraction from spoken transcripts
- Chinese and English text processing
- Key point summarization

## Running All Tests

```bash
# Run from project root
cd /Users/cfh00914977/Project/SlideCue

# Run all integration tests
for test in scripts/integration_tests/test_*.py; do
    echo "Running $test..."
    python "$test"
    echo "---"
done
```

## Notes

- These are **integration tests**, not unit tests
- They require the full application stack to be running
- They make real API calls and may consume OpenAI credits
- Some tests create real database records (use test data)
- Tests are designed to be run manually, not in CI/CD (yet)

## Test Data

Tests either:
- Create their own test PPTX files programmatically
- Use existing decks from the database (ensure you have test data)

## Troubleshooting

**Backend not responding:**
```bash
# Check if backend is running
curl http://localhost:8001/api/health

# Start backend if needed
cd backend
./start-backend.sh
```

**Database issues:**
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Run migrations
cd backend
alembic upgrade head
```

**OpenAI API errors:**
- Verify API key is set in `backend/.env`
- Check you have sufficient credits
- Verify model names are correct in `backend/.env` and `backend/app/core/config.py`
