# SlideCue Service Startup Guide

## Quick Start

### Start All Services
```bash
./start-services.sh
```

This will start:
- Docker containers (PostgreSQL, Redis, MinIO, ChromaDB)
- Backend API (port 8001)
- Celery Worker (with macOS-compatible solo pool)
- Frontend (port 5173)

### Stop All Services
```bash
./stop-services.sh
```

## Service URLs

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8001
- **MinIO Console**: http://localhost:9001 (admin/password: minioadmin/minioadmin)
- **API Docs**: http://localhost:8001/docs

## Logs

View real-time logs:
```bash
# Backend
tail -f logs/backend.log

# Celery Worker
tail -f logs/celery.log

# Frontend
tail -f logs/frontend.log
```

## Important Notes

### Celery Worker on macOS
The Celery worker must run with `--pool=solo` on macOS to avoid forking issues (SIGSEGV crashes) with pdf2image/poppler. This is already configured in the startup script.

### Docker Containers
The basic setup uses `docker-compose.yml` which includes:
- PostgreSQL with pgvector extension (port 5432)
- Redis (port 6379)
- MinIO S3-compatible storage (ports 9000-9001)

ChromaDB is started separately as a standalone Docker container.

### Manual Startup (Alternative)

If you need to start services individually:

1. **Start Docker containers:**
   ```bash
   docker-compose up -d
   docker run -d --name chroma-db -p 8000:8000 -v chroma-data:/chroma/chroma chromadb/chroma
   ```

2. **Start Backend:**
   ```bash
   cd backend
   source venv/bin/activate
   uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
   ```

3. **Start Celery Worker (in another terminal):**
   ```bash
   cd backend
   source venv/bin/activate
   celery -A app.workers.celery_app worker --loglevel=info --pool=solo
   ```

4. **Start Frontend (in another terminal):**
   ```bash
   cd frontend
   npm run dev
   ```

## Troubleshooting

### Port Already in Use
If you get "port already in use" errors, stop all services:
```bash
./stop-services.sh
# Or manually:
lsof -ti:8001 | xargs kill -9  # Backend
lsof -ti:5173 | xargs kill -9  # Frontend
pkill -f "celery.*worker"      # Celery
```

### Deck Analysis Not Working
Check if Celery worker is running:
```bash
ps aux | grep celery
```

If not running, the worker is required for:
- PDF/PPTX file processing
- Slide extraction and image generation
- AI analysis of slides
- Topic card generation

### Worker Crashes (SIGSEGV)
This happens when using default multiprocessing on macOS. Always use `--pool=solo`:
```bash
celery -A app.workers.celery_app worker --loglevel=info --pool=solo
```

### Check Service Health
```bash
# Backend health
curl http://localhost:8001/health

# Check all running processes
ps aux | grep -E "uvicorn|celery|vite"

# Check Docker containers
docker ps
```
