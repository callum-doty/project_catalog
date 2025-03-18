#!/bin/bash
# start.sh - Script to start the application on Railway

set -e  # Exit immediately if a command exits with a non-zero status

# Print environment info for debugging
echo "Starting service with environment: SERVICE_TYPE=${SERVICE_TYPE}"
echo "Current directory: $(pwd)"
echo "Python version: $(python --version)"

# Set secure environment variables when running on Railway
if [ -n "$RAILWAY_ENVIRONMENT" ]; then
    echo "Railway.app environment detected, setting secure environment variables"
    export SECURE_COOKIES=true
    export BEHIND_PROXY=true
    export PREFERRED_URL_SCHEME=https
    echo "✓ Security environment variables set for Railway"
fi

# Create necessary directories
mkdir -p ./data/documents
mkdir -p ./tmp
export TMPDIR=$(pwd)/tmp

# Set the default service type if not specified
SERVICE_TYPE=${SERVICE_TYPE:-"web"}

# Handle service based on type
case $SERVICE_TYPE in
  "web")
    echo "Starting web service..."
    
    # Try to run database migrations
    python -m flask db upgrade || echo "WARNING: Database migrations failed"
    
    # Start the Flask application with proper settings for proxies
    if [ -n "$RAILWAY_ENVIRONMENT" ]; then
        echo "Starting with Railway proxy settings..."
        gunicorn --bind "0.0.0.0:${PORT:-5000}" --workers=1 --timeout=120 --forwarded-allow-ips='*' wsgi:application
    else
        echo "Starting with standard settings..."
        gunicorn --bind "0.0.0.0:${PORT:-5000}" --workers=1 --timeout=120 wsgi:application
    fi
    ;;
    
  "worker")
    echo "Starting Celery worker..."
    
    # List available tasks (for debugging)
    echo "Listing available tasks..."
    python -c "from celery import Celery; app = Celery('tasks'); app.autodiscover_tasks(['tasks'], force=True); print('Available tasks:', list(app.tasks.keys()))"
    
    # Start with very limited concurrency to prevent memory issues
    celery -A tasks worker -Q document_processing,analysis,celery --loglevel=info --concurrency=2
    ;;
    
  "beat")
    echo "Starting Celery beat..."
    
    # Start the beat scheduler with a smaller interval
    celery -A tasks beat --loglevel=info --max-interval=60
    ;;
    
  *)
    echo "ERROR: Unknown service type '${SERVICE_TYPE}'"
    echo "Valid values are: web, worker, beat"
    exit 1
    ;;
esac