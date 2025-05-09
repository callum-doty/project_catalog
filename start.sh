#!/bin/bash
# start.sh - Script to start the application on Railway

set -e  # Exit immediately if a command exits with a non-zero status

# Print environment info for debugging
echo "Starting service in Railway environment"
echo "Environment variables:"
echo "DATABASE_URL=${DATABASE_URL}"

# Fix DATABASE_URL if it contains the literal ${DATABASE_URL}
if [[ "$DATABASE_URL" == '${DATABASE_URL}' ]]; then
    # Try to build from individual Postgres variables
    echo "Warning: DATABASE_URL is not properly expanded, attempting to fix..."
    
    # Use Railway's Postgres variables if available
    if [[ -n "$RAILWAY_VOLUME_POSTGRESQL_DATA_EXTERNAL" ]]; then
        # This is a heuristic to detect if Railway Postgres is linked
        DB_USER="${PGUSER:-custom_user}"
        DB_PASSWORD="${PGPASSWORD:-strong_password}"
        DB_HOST="${PGHOST:-localhost}"
        DB_PORT="${PGPORT:-5432}"
        DB_NAME="${PGDATABASE:-catalog_db}"
        
        export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
        export SQLALCHEMY_DATABASE_URI="$DATABASE_URL"
        
        echo "Fixed DATABASE_URL=$DATABASE_URL"
    fi
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
    exit 1
    ;;
esac