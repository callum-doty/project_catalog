#!/bin/bash
# start.sh - Script to start the application on Railway

set -e  # Exit immediately if a command exits with a non-zero status

# Print environment info for debugging (excluding secrets)
echo "Starting application with Python $(python --version)"
echo "Current directory: $(pwd)"

# Create necessary directories
mkdir -p /data/documents

# Create simple healthy response for healthcheck
mkdir -p app/static
echo "Healthy" > app/static/health.txt

# Check if the database is available and run migrations
echo "Running database migrations..."
python -m flask db upgrade || echo "Warning: Migrations failed, continuing anyway"

# Start the application with gunicorn
echo "Starting gunicorn on PORT ${PORT:-5000}..."
exec gunicorn --bind "0.0.0.0:${PORT:-5000}" wsgi:application