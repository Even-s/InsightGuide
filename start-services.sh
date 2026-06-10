#!/bin/bash

# Start InsightGuide services
echo "🚀 Starting InsightGuide services..."

# Start Docker containers (databases and storage)
echo "📦 Starting Docker containers..."
docker-compose -f docker-compose.yml up -d

# Wait for containers to be healthy
echo "⏳ Waiting for containers to be ready..."
sleep 5

# Check if containers are running
docker ps --filter "name=insightguide"

# Start backend
echo "🔧 Starting backend on port 8002..."
cd backend
source venv/bin/activate

# Kill any existing processes on ports
lsof -ti:8002 | xargs kill -9 2>/dev/null || true

# Start backend in background
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend started (PID: $BACKEND_PID)"

# Start Celery worker with solo pool (macOS compatible)
echo "👷 Starting Celery worker..."
celery -A app.workers.celery_app worker --loglevel=info --pool=solo > ../logs/celery.log 2>&1 &
CELERY_PID=$!
echo "Celery worker started (PID: $CELERY_PID)"

cd ..

# Start frontend
echo "⚛️  Starting frontend on port 5174..."
cd frontend

# Kill any existing processes on ports
lsof -ti:5174 | xargs kill -9 2>/dev/null || true

npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "Frontend started (PID: $FRONTEND_PID)"

cd ..

# Create logs directory if it doesn't exist
mkdir -p logs

# Save PIDs for easy stopping later
echo $BACKEND_PID > logs/backend.pid
echo $CELERY_PID > logs/celery.pid
echo $FRONTEND_PID > logs/frontend.pid

echo ""
echo "✅ All services started!"
echo ""
echo "📝 Service URLs:"
echo "   Frontend:  http://localhost:5174"
echo "   Backend:   http://localhost:8002"
echo "   MinIO:     http://localhost:9001"
echo ""
echo "📋 Logs:"
echo "   Backend:   tail -f logs/backend.log"
echo "   Celery:    tail -f logs/celery.log"
echo "   Frontend:  tail -f logs/frontend.log"
echo ""
echo "🛑 To stop all services, run: ./stop-services.sh"
