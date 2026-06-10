# SlideCue Quick Start Guide

This guide will help you set up and run SlideCue locally in under 10 minutes.

## Prerequisites

- Docker and Docker Compose installed
- Node.js 18+ and npm installed
- Python 3.11+ installed
- OpenAI API key

## Step-by-Step Setup

### 1. Environment Setup

```bash
# Copy environment files
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# Edit .env and add your OpenAI API key
# OPENAI_API_KEY=sk-your-api-key-here
```

### 2. Start Infrastructure

```bash
# Start PostgreSQL, Redis, and MinIO
docker-compose up -d

# Verify services are running
docker-compose ps
```

All services should show status as "healthy" after a few seconds.

### 3. Setup Backend

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
# Note: Alembic migrations need to be created first
# For now, you can create tables manually or run:
# python -c "from app.db.session import Base, engine; Base.metadata.create_all(bind=engine)"
```

### 4. Start Backend Services

```bash
# Terminal 1: Start FastAPI server
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start Celery worker
cd backend
source venv/bin/activate
celery -A app.workers.celery_app worker --loglevel=info
```

### 5. Setup Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

## Access the Application

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)

## Verify Setup

1. Open http://localhost:5173 in your browser
2. You should see the SlideCue upload page
3. Visit http://localhost:8000/health to verify backend is running
4. Check http://localhost:8000/docs for API documentation

## Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# View PostgreSQL logs
docker-compose logs postgres

# Restart PostgreSQL
docker-compose restart postgres
```

### Redis Connection Issues

```bash
# Check Redis is running
docker-compose ps redis

# Test Redis connection
docker-compose exec redis redis-cli ping
```

### Backend Import Errors

```bash
# Ensure virtual environment is activated
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Reinstall dependencies
pip install -r requirements.txt
```

### Frontend Port Conflicts

If port 5173 is already in use, Vite will automatically use the next available port. Check the terminal output for the actual port number.

## Next Steps

Now that your environment is set up, you're ready to start development:

1. Read `SlideCue_開發架構書.md` for architectural guidance
2. Check `README.md` for detailed project information
3. Review the MVP milestones to understand the development roadmap
4. Start with Milestone 1: PPTX Upload + PDF Conversion

## Development Workflow

```bash
# Backend
cd backend
source venv/bin/activate

# Run tests
pytest

# Format code
black .
isort .

# Type check
mypy .

# Frontend
cd frontend

# Run tests
npm test

# Lint
npm run lint

# Type check
npm run type-check
```

## Stopping Services

```bash
# Stop backend (Ctrl+C in each terminal)

# Stop frontend (Ctrl+C)

# Stop infrastructure
docker-compose down

# Stop infrastructure and remove volumes (WARNING: deletes all data)
docker-compose down -v
```
