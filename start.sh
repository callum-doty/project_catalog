#!/bin/bash
# start.sh - Script to start the application on Railway

set -e  # Exit immediately if a command exits with a non-zero status

echo "Starting service with enhanced debugging..."

# Use the Railway-provided postgres variables if available
if [[ -n "$PGHOST" && -n "$PGUSER" && -n "$PGPASSWORD" && -n "$PGDATABASE" ]]; then
    echo "Found PostgreSQL variables, setting DATABASE_URL explicitly"
    export DATABASE_URL="postgresql://${PGUSER}:${PGPASSWORD}@${PGHOST}:${PGPORT:-5432}/${PGDATABASE}"
    export SQLALCHEMY_DATABASE_URI="$DATABASE_URL"
    echo "Explicitly set DATABASE_URL (masked password)"
    echo "DATABASE_URL=postgresql://${PGUSER}:********@${PGHOST}:${PGPORT:-5432}/${PGDATABASE}"
else
    echo "WARNING: PostgreSQL variables not found!"
    # Set a hardcoded URL for testing/fallback
    export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/postgres"
    export SQLALCHEMY_DATABASE_URI="$DATABASE_URL"
    echo "Set hardcoded fallback DATABASE_URL for testing"
fi

# Create necessary directories
mkdir -p ./data/documents
mkdir -p ./tmp
export TMPDIR=$(pwd)/tmp

# Try to run database migrations (but don't fail if they fail)
echo "Running database migrations..."
FLASK_APP=src/wsgi.py python -m flask db upgrade || echo "WARNING: Database migrations failed"

# Start the Flask application with proper settings for proxies
if [ -n "$RAILWAY_ENVIRONMENT" ]; then
    echo "Starting with Railway proxy settings..."
    gunicorn --bind "0.0.0.0:${PORT:-5000}" --workers=1 --timeout=120 --forwarded-allow-ips='*' src.wsgi:application
else
    echo "Starting with standard settings..."
    gunicorn --bind "0.0.0.0:${PORT:-5000}" --workers=1 --timeout=120 src.wsgi:application
fi

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
    
    # Wait for database to be ready
    echo "Waiting for database connection..."
    MAX_RETRIES=30
    count=0
    while [ $count -lt $MAX_RETRIES ]; do
      count=$((count+1))
      pg_isready -h ${DATABASE_HOST:-postgres} -p ${DATABASE_PORT:-5432} -U ${DATABASE_USER:-postgres} && break
      echo "Retry $count/$MAX_RETRIES - database not ready yet..."
      sleep 2
    done

    # Run migrations with better error handling
    echo "Running database migrations..."
    FLASK_APP=src/wsgi.py python -m flask db upgrade || {
      echo "WARNING: Database migrations failed - checking database status..."
      # Try to initialize database if empty
      FLASK_APP=src/wsgi.py python -m flask db init || true
      FLASK_APP=src/wsgi.py python -m flask db migrate || true
      FLASK_APP=src/wsgi.py python -m flask db upgrade || true
    }
    
    # Start the Flask application with proper settings for proxies
    if [ -n "$RAILWAY_ENVIRONMENT" ]; then
        echo "Starting with Railway proxy settings..."
        gunicorn --bind "0.0.0.0:${PORT:-5000}" --workers=1 --timeout=120 --forwarded-allow-ips='*' src.wsgi:application
    else
        echo "Starting with standard settings..."
        gunicorn --bind "0.0.0.0:${PORT:-5000}" --workers=1 --timeout=120 src.wsgi:application
    fi
    ;;
    
  "worker")
    echo "Starting Celery worker..."
    
    # List available tasks (for debugging)
    echo "Listing available tasks..."
    python -c "import sys; print('Python path:', sys.path); from src.catalog.tasks.celery_app import celery_app; print('Available tasks:', list(celery_app.tasks.keys()))"
    
    # Start with very limited concurrency to prevent memory issues
    celery -A src.catalog.tasks.celery_app worker -Q document_processing,analysis,celery --loglevel=info --concurrency=2
    ;;
    
  "beat")
    echo "Starting Celery beat..."
    
    # Start the beat scheduler with a smaller interval
    celery -A src.catalog.tasks.celery_app beat --loglevel=info --max-interval=60
    ;;
    
  *)
    echo "ERROR: Unknown service type '${SERVICE_TYPE}'"
    echo "Valid values are: web, worker, beat"
    echo "Environment variables for debugging:"
    echo "PGUSER: ${PGUSER:-not set}"
    echo "PGPASSWORD: ${PGPASSWORD:-not set}"
    echo "PGHOST: ${PGHOST:-not set}"
    echo "PGPORT: ${PGPORT:-not set}"
    echo "PGDATABASE: ${PGDATABASE:-not set}"
    echo "DATABASE_URL: ${DATABASE_URL:-not set}"
    echo "SQLALCHEMY_DATABASE_URI: ${SQLALCHEMY_DATABASE_URI:-not set}"
    exit 1
    ;;
esac