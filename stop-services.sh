#!/bin/bash

# Stop InsightGuide services
echo "🛑 Stopping InsightGuide services..."

# Stop Docker containers
echo "📦 Stopping Docker containers..."
docker-compose -f docker-compose.yml down

# Stop backend, celery, and frontend using saved PIDs
if [ -f logs/backend.pid ]; then
    BACKEND_PID=$(cat logs/backend.pid)
    kill $BACKEND_PID 2>/dev/null && echo "Backend stopped (PID: $BACKEND_PID)" || echo "Backend not running"
    rm logs/backend.pid
fi

if [ -f logs/celery.pid ]; then
    CELERY_PID=$(cat logs/celery.pid)
    kill $CELERY_PID 2>/dev/null && echo "Celery worker stopped (PID: $CELERY_PID)" || echo "Celery not running"
    rm logs/celery.pid
fi

if [ -f logs/frontend.pid ]; then
    FRONTEND_PID=$(cat logs/frontend.pid)
    kill $FRONTEND_PID 2>/dev/null && echo "Frontend stopped (PID: $FRONTEND_PID)" || echo "Frontend not running"
    rm logs/frontend.pid
fi

# Fallback: kill by port
lsof -ti:8002 | xargs kill -9 2>/dev/null || true
lsof -ti:5174 | xargs kill -9 2>/dev/null || true
pkill -f "celery.*worker" 2>/dev/null || true

echo "✅ All services stopped!"
