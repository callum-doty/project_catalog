#!/bin/bash
# start.sh - Script to start the application on Railway with fixed connection fallback

set -e  # Exit immediately if a command exits with a non-zero status

echo "Starting service with enhanced debugging..."

# Debug variables
echo "Current directory: $(pwd)"
echo "Python version: $(python --version)"
echo "Files in current directory: $(ls -la)"

# Hard-coded Railway PostgreSQL connection details as fallback
RAILWAY_DB_HOST="shinkansen.proxy.rlwy.net"
RAILWAY_DB_PORT="52940"
RAILWAY_DB_NAME="railway"
RAILWAY_DB_USER="postgres"
RAILWAY_DB_PASSWORD="ktUhwMMfeuiDxLHwSNLoEwGfPoenjCZI"
RAILWAY_DB_URL="postgresql://${RAILWAY_DB_USER}:${RAILWAY_DB_PASSWORD}@${RAILWAY_DB_HOST}:${RAILWAY_DB_PORT}/${RAILWAY_DB_NAME}"

# Check if we're running in Railway's environment
if [ -n "$RAILWAY_ENVIRONMENT" ]; then
    echo "✅ Detected Railway environment: $RAILWAY_ENVIRONMENT"
    
    # Try to use the Railway PostgreSQL variables if they exist
    if [ -n "$PGHOST" ] && [ -n "$PGUSER" ] && [ -n "$PGPASSWORD" ] && [ -n "$PGDATABASE" ]; then
        echo "✅ Using Railway PostgreSQL variables"
        export DATABASE_URL="postgresql://${PGUSER}:${PGPASSWORD}@${PGHOST}:${PGPORT:-5432}/${PGDATABASE}"
        export SQLALCHEMY_DATABASE_URI="$DATABASE_URL"
        echo "Set DATABASE_URL from Railway PostgreSQL variables"
        
    # If DATABASE_URL is already set, use it
    elif [ -n "$DATABASE_URL" ]; then
        echo "✅ Using existing DATABASE_URL"
        export SQLALCHEMY_DATABASE_URI="$DATABASE_URL"
        echo "Set SQLALCHEMY_DATABASE_URI from DATABASE_URL"
        
    # Otherwise, use our hard-coded fallback
    else
        echo "⚠️ No database variables found. Using hardcoded fallback."
        export DATABASE_URL="$RAILWAY_DB_URL"
        export SQLALCHEMY_DATABASE_URI="$RAILWAY_DB_URL"
        export PGHOST="$RAILWAY_DB_HOST"
        export PGPORT="$RAILWAY_DB_PORT"
        export PGDATABASE="$RAILWAY_DB_NAME"
        export PGUSER="$RAILWAY_DB_USER"
        export PGPASSWORD="$RAILWAY_DB_PASSWORD"
        echo "Set database connection with hardcoded fallback values"
    fi
    
    # Print connection strings (masking password)
    MASKED_URL=$(echo "$DATABASE_URL" | sed 's/:[^:]*@/:*****@/')
    echo "Using DATABASE_URL: $MASKED_URL"
else
    echo "⚠️ Not running in Railway environment - using local settings"
    export DATABASE_URL="postgresql://custom_user:strong_password@localhost:5432/catalog_db"
    export SQLALCHEMY_DATABASE_URI="$DATABASE_URL"
fi

# Set secure environment variables
export SECURE_COOKIES=true
export BEHIND_PROXY=true
export PREFERRED_URL_SCHEME=https

# Create necessary directories
mkdir -p ./data/documents
mkdir -p ./tmp
export TMPDIR=$(pwd)/tmp

# Create database schema if it doesn't exist yet
echo "Checking database connection and setting up schema if needed..."
python -c "
import psycopg2, os
try:
    conn_str = os.environ.get('DATABASE_URL')
    if conn_str.startswith('postgres://'):
        conn_str = conn_str.replace('postgres://', 'postgresql://', 1)
    conn = psycopg2.connect(conn_str)
    cur = conn.cursor()
    cur.execute('SELECT 1')
    print('✅ Database connection successful')
    conn.close()
except Exception as e:
    print(f'❌ Database connection failed: {str(e)}')
    exit(1)
"

# Try to run migrations
echo "Running database migrations..."
FLASK_APP=src/wsgi.py python -m flask db upgrade || echo "WARNING: Database migrations failed, continuing anyway"

# Start the Flask application
echo "Starting application..."
gunicorn --bind "0.0.0.0:${PORT:-5000}" --workers=1 --timeout=120 --forwarded-allow-ips='*' src.wsgi:application