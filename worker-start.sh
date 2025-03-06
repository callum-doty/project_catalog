#!/bin/bash
# Startup script for Celery worker

# Print diagnostic information
echo "Starting Celery worker service"
echo "Current directory: $(pwd)"
echo "Python version: $(python --version)"

# Create necessary directories
mkdir -p ./data/documents
mkdir -p ./tmp
export TMPDIR=$(pwd)/tmp

# Try to run migrations (but don't fail if they fail)
echo "Skipping migrations for worker service"

# Start the Celery worker
echo "Starting Celery worker..."
celery -A tasks worker -Q document_processing,analysis --loglevel=info