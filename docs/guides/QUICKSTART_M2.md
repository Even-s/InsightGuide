# Quick Start: Milestone 2 Testing

Get Milestone 2 (AI Slide Analysis) running in under 5 minutes.

## Prerequisites

- Docker and Docker Compose installed
- OpenAI API key ([Get one here](https://platform.openai.com/api-keys))

## Steps

### 1. Configure Environment

```bash
cd /path/to/SlideCue

# Create .env file
cp .env.example .env

# Add your OpenAI API key
nano .env  # or use your favorite editor
# Set: OPENAI_API_KEY=sk-your-actual-key-here
```

### 2. Start Services

```bash
# One command to start everything
./start-docker.sh

# Wait ~30 seconds for services to initialize
```

Expected output:
```
✅ SlideCue is ready!
📍 Service URLs:
   Backend API:  http://localhost:8001
   API Docs:     http://localhost:8001/docs
```

### 3. Test It

```bash
# Install test dependencies (one-time)
pip3 install requests python-pptx

# Run Milestone 2 test
python3 test_milestone2_fixed.py
```

Expected flow:
1. ✅ Creates test PPTX with 3 slides
2. ✅ Uploads to API
3. ✅ Monitors: uploaded → processing → converted → analyzing → analyzed
4. ✅ Retrieves topic cards
5. ✅ Verifies coverage rules

Typical runtime: **60-90 seconds** (depends on OpenAI API response time)

### 4. Explore Results

Visit http://localhost:8001/docs and try:

1. **Upload your own PPTX**:
   - POST `/api/decks/` 
   - Attach a PPTX file
   - Note the returned `deck_id`

2. **Monitor progress**:
   - GET `/api/decks/{deck_id}/status`
   - Watch status change: uploaded → processing → converted → analyzing → analyzed

3. **View analysis**:
   - GET `/api/decks/{deck_id}/analysis`
   - See slides and topic card counts

4. **Get topic cards**:
   - GET `/api/topic-cards/deck/{deck_id}`
   - See AI-generated cards with coverage rules

## What Gets Analyzed

For each slide, AI generates:

✅ **Slide Summary** - One-sentence overview  
✅ **Topic Cards** (1-3 per slide):
  - Title and description
  - Importance (must/should/optional)
  - Topic type (problem/solution/data/etc)
  - **Coverage Rules**:
    - Semantic anchors (core concepts)
    - Expected keywords (5-15 terms)
    - Must-mention facts (required information)
    - Scoring thresholds
  - Suggested script (natural language)
  - Estimated speaking time

## Example Topic Card

```json
{
  "title": "機器學習三大類型",
  "importance": "must",
  "coverageRule": {
    "semanticAnchors": [
      "機器學習分為監督式、非監督式和強化學習三種"
    ],
    "expectedKeywords": [
      "監督式", "非監督式", "強化學習", "訓練資料"
    ],
    "mustMentionFacts": [
      {
        "text": "三種主要類型",
        "required": true
      }
    ],
    "thresholds": {
      "covered": 0.78
    }
  },
  "suggestedScript": "機器學習主要分成三大類..."
}
```

## Troubleshooting

### Services won't start
```bash
# Check Docker is running
docker ps

# Check logs
docker-compose -f docker-compose.full.yml logs
```

### Upload fails
```bash
# Check backend logs
docker logs slidecue-backend

# Verify OpenAI key is set
docker exec slidecue-backend env | grep OPENAI_API_KEY
```

### Worker not processing
```bash
# Check worker logs
docker logs -f slidecue-worker

# Common issues:
# - OpenAI API key not set
# - Rate limit reached (wait and retry)
# - Network connectivity
```

### Status stuck on "analyzing"
```bash
# Check worker is running
docker ps | grep worker

# View worker logs
docker logs -f slidecue-worker

# Look for OpenAI API errors
```

## Clean Up

```bash
# Stop all services
docker-compose -f docker-compose.full.yml down

# Stop and remove all data
docker-compose -f docker-compose.full.yml down -v
```

## Next Steps

Once Milestone 2 works:

1. **Try your own presentations** - Upload real PPTX files
2. **Review topic cards** - Check if AI captured key points
3. **Explore API** - Build custom integrations
4. **Milestone 3** - Start building the Editor Mode UI

## Need Help?

- **Full documentation**: See `DOCKER_SETUP.md`
- **Implementation details**: See `MILESTONE_2_SUMMARY.md`
- **Architecture**: See `SlideCue_開發架構書.md`
- **API docs**: http://localhost:8001/docs (when running)

## Performance Notes

- **First upload**: May take 60-90 seconds (PPTX conversion + AI analysis)
- **Large decks**: +10-15 seconds per additional slide
- **Cost**: ~$0.01-0.05 per slide (OpenAI API)

## What's Different from Milestone 1?

**Milestone 1**: Upload → Convert → Extract  
**Milestone 2**: ✨ + AI Analysis → Topic Cards → Coverage Rules

The Docker solution ensures LibreOffice and Poppler are available, making the full pipeline work seamlessly.

---

**Happy testing! 🎉**
