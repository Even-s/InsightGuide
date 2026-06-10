# Docker Setup for SlideCue

This guide explains how to run SlideCue with all dependencies (LibreOffice, Poppler) using Docker.

## Prerequisites

- Docker and Docker Compose installed
- OpenAI API key

## Quick Start

### 1. Set Environment Variables

Create a `.env` file in the project root:

```bash
# Copy from example
cp .env.example .env

# Edit and add your OpenAI API key
# OPENAI_API_KEY=sk-your-api-key-here
```

### 2. Start All Services with Docker

```bash
# Start infrastructure + backend + worker
docker-compose -f docker-compose.full.yml up -d

# Check status
docker-compose -f docker-compose.full.yml ps
```

This will start:
- **PostgreSQL** with pgvector (port 5432)
- **Redis** (port 6379)
- **MinIO** (ports 9000, 9001)
- **Backend API** (port 8001)
- **Celery Worker** with LibreOffice + Poppler

### 3. Run Database Migrations

```bash
# Run migrations in the backend container
docker exec -it slidecue-backend alembic upgrade head

# Create default user
docker exec -it slidecue-backend python -c "
from app.db.session import SessionLocal
from app.models.user import User
from datetime import datetime

db = SessionLocal()
user = db.query(User).filter(User.id == 'user_default').first()
if not user:
    user = User(
        id='user_default',
        email='default@example.com',
        created_at=datetime.utcnow()
    )
    db.add(user)
    db.commit()
    print('Default user created')
else:
    print('Default user already exists')
db.close()
"
```

### 4. Test the Setup

```bash
# Test backend health
curl http://localhost:8001/health

# Test API docs
open http://localhost:8001/docs
```

### 5. Run Milestone 2 Test

```bash
# Install test dependencies locally
pip install requests python-pptx

# Run the test
python3 test_milestone2_fixed.py
```

## Service URLs

- **Backend API**: http://localhost:8001
- **API Documentation**: http://localhost:8001/docs
- **MinIO Console**: http://localhost:9001 (minioadmin / minioadmin)
- **PostgreSQL**: localhost:5432 (slidecue / slidecue_password)
- **Redis**: localhost:6379

## Docker Commands

### View Logs

```bash
# All services
docker-compose -f docker-compose.full.yml logs -f

# Specific service
docker-compose -f docker-compose.full.yml logs -f worker
docker-compose -f docker-compose.full.yml logs -f backend

# Worker logs (for debugging conversion issues)
docker logs -f slidecue-worker
```

### Restart Services

```bash
# Restart worker (e.g., after code changes)
docker-compose -f docker-compose.full.yml restart worker

# Restart backend
docker-compose -f docker-compose.full.yml restart backend

# Restart all
docker-compose -f docker-compose.full.yml restart
```

### Stop Services

```bash
# Stop all services
docker-compose -f docker-compose.full.yml down

# Stop and remove volumes (clean slate)
docker-compose -f docker-compose.full.yml down -v
```

### Rebuild After Code Changes

```bash
# Rebuild and restart backend and worker
docker-compose -f docker-compose.full.yml build backend worker
docker-compose -f docker-compose.full.yml up -d backend worker
```

## Development Workflow

### Option 1: Full Docker (Recommended for Milestone 2 Testing)

Run everything in Docker, including backend and workers. This ensures LibreOffice and Poppler are available.

```bash
docker-compose -f docker-compose.full.yml up -d
```

### Option 2: Hybrid (Docker for Infrastructure, Local for Backend)

Run only infrastructure in Docker, but run backend and workers locally. This is faster for development but requires LibreOffice and Poppler installed locally.

```bash
# Start infrastructure only
docker-compose up -d

# Run backend locally
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Run worker locally (in another terminal)
cd backend
source venv/bin/activate
celery -A app.workers.celery_app worker --loglevel=info
```

**Note**: For Option 2, you need to install:
- macOS: `brew install poppler` (requires Homebrew)
- Linux: `sudo apt-get install poppler-utils libreoffice`

### Option 3: Worker in Docker, Backend Local

Run worker in Docker (for LibreOffice/Poppler), but backend locally for faster iteration:

```bash
# Start infrastructure + worker
docker-compose -f docker-compose.full.yml up -d postgres redis minio worker

# Run backend locally
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

## Troubleshooting

### Worker Crashes

```bash
# Check worker logs
docker logs -f slidecue-worker

# Common issues:
# - LibreOffice not found: Check Dockerfile includes libreoffice
# - Poppler not found: Check Dockerfile includes poppler-utils
# - Out of memory: Increase Docker memory limit
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker-compose -f docker-compose.full.yml ps postgres

# Check if database exists
docker exec -it slidecue-postgres psql -U slidecue -d slidecue -c "\dt"
```

### MinIO Connection Issues

```bash
# Check MinIO is running
docker-compose -f docker-compose.full.yml ps minio

# Access MinIO console
open http://localhost:9001

# Check bucket exists (should be created automatically)
```

### OpenAI API Issues

```bash
# Check API key is set in backend container
docker exec -it slidecue-backend env | grep OPENAI_API_KEY

# If empty, ensure .env file is in project root with OPENAI_API_KEY
```

## File Structure

```
SlideCue/
├── docker-compose.yml              # Infrastructure only (original)
├── docker-compose.full.yml         # Full stack (infrastructure + app)
├── .env                            # Environment variables (create this)
├── .env.example                    # Template
├── backend/
│   ├── Dockerfile                  # Backend + Worker image
│   ├── requirements.txt
│   └── app/
├── test_milestone2_fixed.py        # Test script
└── DOCKER_SETUP.md                 # This file
```

## Environment Variables

Key variables in `.env`:

```bash
# Required
OPENAI_API_KEY=sk-xxx

# Optional (defaults shown)
POSTGRES_USER=slidecue
POSTGRES_PASSWORD=slidecue_password
POSTGRES_DB=slidecue
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
```

## Next Steps

After setup is complete:

1. **Test Milestone 1**: Upload PPTX → PDF conversion → Slide extraction
2. **Test Milestone 2**: AI analysis → Topic card generation
3. **Develop Milestone 3**: Editor Mode UI

## Performance Notes

- **Worker concurrency**: Default is 4. Adjust in `docker-compose.full.yml`:
  ```yaml
  command: celery -A app.workers.celery_app worker --loglevel=info --concurrency=8
  ```

- **Memory**: LibreOffice and PDF processing are memory-intensive. Ensure Docker has at least 4GB RAM allocated.

- **Storage**: Slide images and PDFs are stored in MinIO. Check usage:
  ```bash
  docker exec -it slidecue-minio du -sh /data
  ```

## Clean Up

```bash
# Stop and remove all containers, networks
docker-compose -f docker-compose.full.yml down

# Also remove volumes (deletes all data)
docker-compose -f docker-compose.full.yml down -v

# Remove images
docker rmi slidecue-backend slidecue-worker
```
