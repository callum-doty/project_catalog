#!/bin/bash
# start.sh - Script that detects which service to start

set -e  # Exit immediately if a command exits with a non-zero status

# Print environment info for debugging
echo "Starting application with Python $(python --version)"
echo "Current directory: $(pwd)"

# Create necessary directories
mkdir -p ./data/documents
mkdir -p ./tmp
export TMPDIR=$(pwd)/tmp

echo "Starting Celery worker with limited concurrency..."
celery -A tasks worker -Q document_processing,analysis --loglevel=info --concurrency=2

# Create health check file for web service
mkdir -p app/static
echo "Healthy" > app/static/health.txt

# Detect which service to start based on an environment variable
SERVICE_TYPE=${SERVICE_TYPE:-"web"}
echo "Starting service type: $SERVICE_TYPE"

case $SERVICE_TYPE in
  "web")
    echo "Starting web service..."
    # Try to run migrations (but continue if they fail)
    python -m flask db upgrade || echo "Warning: Migrations failed, continuing anyway"
    # Start the web server
    gunicorn --workers=1 --bind "0.0.0.0:${PORT}" wsgi:application
    ;;
  "worker")
    echo "Starting Celery worker..."
    celery -A tasks worker -Q document_processing,analysis --loglevel=info
    ;;
  "beat")
    echo "Starting Celery beat..."
    celery -A tasks beat --loglevel=info
    ;;
  *)
    echo "Unknown service type: $SERVICE_TYPE"
    exit 1
    ;;
esac