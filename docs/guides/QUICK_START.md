# SlideCue Quick Start

Get SlideCue up and running in minutes!

## Prerequisites

- Docker Desktop running
- Python 3.9+ with virtualenv
- Node.js 18+ with npm

## One-Command Startup

```bash
../../start-services.sh
```

This script will:
1. ✅ Start Docker services (PostgreSQL, Redis, MinIO)
2. ✅ Run database migrations
3. ✅ Start Backend API (port 8001)
4. ✅ Start Celery worker (background tasks)
5. ✅ Start Frontend dev server (port 5173)

## Access the Application

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8001
- **API Documentation**: http://localhost:8001/docs
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)

## Check Status

```bash
./status.sh
```

See real-time status of all services, health checks, and logs.

## Stop All Services

```bash
../../stop-services.sh
```

Gracefully stops all SlideCue services and Docker containers.

## View Logs

```bash
# Backend logs
tail -f logs/backend.log

# Celery worker logs
tail -f logs/celery.log

# Frontend logs
tail -f logs/frontend.log
```

## Troubleshooting

### Deck stuck in "preparing" status

**Problem**: Celery worker not running
```bash
# Check worker status
./status.sh

# Restart worker if needed
../../restart-all.sh
```

### Cannot upload files

**Problem**: MinIO not configured
```bash
# Check MinIO is running
docker ps | grep minio

# Access console to verify bucket
open http://localhost:9001
```

### Backend errors

**Problem**: Database or Redis connection issues
```bash
# Check infrastructure services
docker-compose ps

# Restart if needed
docker-compose restart
```

## Manual Startup (for Development)

If you prefer to run services in separate terminals for better log visibility:

### Terminal 1: Infrastructure
```bash
docker-compose up
```

### Terminal 2: Backend
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

### Terminal 3: Celery Worker
```bash
cd backend
source venv/bin/activate
celery -A app.worker worker --loglevel=info
```

### Terminal 4: Frontend
```bash
cd frontend
npm run dev
```

## First Time Setup

### 1. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env` file:
```bash
cp .env.example .env
# Edit .env with your OpenAI API key
```

### 2. Frontend Setup

```bash
cd frontend
npm install
```

Create `.env` file:
```bash
echo "VITE_API_BASE_URL=http://localhost:8001" > .env
```

### 3. Start Infrastructure

```bash
docker-compose up -d
```

### 4. Run Migrations

```bash
cd backend
source venv/bin/activate
alembic upgrade head
```

### 5. Start Services

```bash
../../start-services.sh
```

## Next Steps

1. **Upload a Deck**
   - Go to http://localhost:5173
   - Click "Upload New Deck"
   - Upload a PDF or PPTX file

2. **Wait for Analysis**
   - Deck will process in the background
   - Status changes from "preparing" to "ready"
   - Watch Celery logs: `tail -f logs/celery.log`

3. **Start Presenting**
   - Click on your prepared deck
   - Click "Start Presentation"
   - Speak and see real-time transcript & topic cards

## Full Documentation

For complete documentation, see [STARTUP.md](STARTUP.md)

## Support

- Check service status: `./status.sh`
- View logs: `tail -f logs/*.log`
- API documentation: http://localhost:8001/docs
- Restart everything: `../../restart-all.sh`
