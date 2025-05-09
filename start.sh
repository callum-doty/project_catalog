#!/bin/bash
# start.sh - Script to start the application on Railway

set -e  # Exit immediately if a command exits with a non-zero status

echo "Starting service with enhanced debugging..."

# Debug information
echo "Environment variables for debugging:"
python railway_debug.py || echo "Debug script failed"

# Check for Railway's PostgreSQL variables
if [[ -n "$RAILWAY_ENVIRONMENT" ]]; then
    echo "✅ Railway environment detected"
    
    # Check if PostgreSQL variables are available
    if [[ -n "$PGHOST" && -n "$PGUSER" && -n "$PGPASSWORD" && -n "$PGDATABASE" ]]; then
        echo "✅ Railway PostgreSQL variables found"
        export DATABASE_URL="postgresql://${PGUSER}:${PGPASSWORD}@${PGHOST}:${PGPORT:-5432}/${PGDATABASE}"
        export SQLALCHEMY_DATABASE_URI="$DATABASE_URL"
        echo "DATABASE_URL set using Railway PostgreSQL variables (password masked)"
    
    # Check for explicit DATABASE_URL provided by Railway
    elif [[ -n "$DATABASE_URL" ]]; then
        echo "✅ DATABASE_URL provided by Railway"
        export SQLALCHEMY_DATABASE_URI="$DATABASE_URL"
        echo "SQLALCHEMY_DATABASE_URI set from DATABASE_URL"
    
    else
        echo "⚠️ No database connection information found in environment!"
        echo "Checking for alternative variables..."
        
        # Try other possible variable names
        if [[ -n "$RAILWAY_POSTGRESQL_URL" ]]; then
            echo "Found RAILWAY_POSTGRESQL_URL, using it"
            export DATABASE_URL="$RAILWAY_POSTGRESQL_URL"
            export SQLALCHEMY_DATABASE_URI="$RAILWAY_POSTGRESQL_URL"
        elif [[ -n "$POSTGRES_URL" ]]; then
            echo "Found POSTGRES_URL, using it"
            export DATABASE_URL="$POSTGRES_URL"
            export SQLALCHEMY_DATABASE_URI="$POSTGRES_URL"
        else
            echo "❌ ERROR: No database connection information found!"
            echo "Please set DATABASE_URL or PostgreSQL variables in Railway"
            exit 1
        fi
    fi
else
    echo "⚠️ Not running in Railway environment"
    # Set a fallback URL for local development
    if [[ -z "$DATABASE_URL" ]]; then
        export DATABASE_URL="postgresql://custom_user:strong_password@localhost:5432/catalog_db"
        export SQLALCHEMY_DATABASE_URI="$DATABASE_URL"
        echo "Set fallback DATABASE_URL for local development"
    fi
fi

echo "Final connection string (password masked):"
CONNECTION_STRING=$(echo "$DATABASE_URL" | sed 's/:[^:]*@/:*****@/')
echo "$CONNECTION_STRING"

# Set secure environment variables when running on Railway
if [ -n "$RAILWAY_ENVIRONMENT" ]; then
    echo "Setting secure environment variables for Railway"
    export SECURE_COOKIES=true
    export BEHIND_PROXY=true
    export PREFERRED_URL_SCHEME=https
fi

# Create necessary directories
mkdir -p ./data/documents
mkdir -p ./tmp
export TMPDIR=$(pwd)/tmp

# Try to run database migrations
echo "Running database migrations..."
FLASK_APP=src/wsgi.py python -m flask db upgrade || echo "WARNING: Database migrations failed, continuing anyway"

# Start the Flask application with proper settings for proxies
echo "Starting application..."
gunicorn --bind "0.0.0.0:${PORT:-5000}" --workers=1 --timeout=120 --forwarded-allow-ips='*' src.wsgi:application