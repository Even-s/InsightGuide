# Backend + Worker Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for temporary files
RUN mkdir -p /tmp/insightguide

# Expose port for API (if running web server in this container)
EXPOSE 8001

# Default command (can be overridden in docker-compose)
CMD ["celery", "-A", "app.workers.celery_app", "worker", "--loglevel=info"]
