#!/bin/bash
# Improved start script for Railway deployment

# Print diagnostic information
echo "Starting service with environment: SERVICE_TYPE=${SERVICE_TYPE}"
echo "Current directory: $(pwd)"
echo "Python version: $(python --version)"

# Make sure REDIS_URL is properly referenced
if [ -n "$REDIS_URL" ]; then
  echo "Redis URL is set"
  # Sanitize the URL before printing (for security)
  SAFE_URL=$(echo $REDIS_URL | sed 's/redis:\/\/[^@]*@/redis:\/\/****:****@/')
  echo "Using Redis URL: $SAFE_URL"
else
  echo "WARNING: REDIS_URL is not set!"
fi

# Create necessary directories
mkdir -p ./data/documents
mkdir -p ./tmp
export TMPDIR=$(pwd)/tmp

# Create health check endpoint for Railway
mkdir -p ./app/static
echo "OK" > ./app/static/health.txt

# Set the default service type if not specified
SERVICE_TYPE=${SERVICE_TYPE:-"web"}

# Handle service based on type
case $SERVICE_TYPE in
  "web")
    echo "Starting web service..."
    
    # Try to run database migrations
    python -m flask db upgrade || echo "WARNING: Database migrations failed"
    
    # Start the Flask application
    gunicorn --bind "0.0.0.0:${PORT:-5000}" --workers=1 --timeout=120 wsgi:application
    ;;
    
  "worker")
    echo "Starting Celery worker..."
    
    # Start with very limited concurrency to prevent memory issues
    celery -A tasks worker -Q document_processing,analysis --loglevel=info --concurrency=2
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