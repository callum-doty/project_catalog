#!/bin/bash
# Startup script for Celery beat

# Print diagnostic information
echo "Starting Celery beat service"
echo "Current directory: $(pwd)"
echo "Python version: $(python --version)"

# Create necessary directories
mkdir -p ./data/documents
mkdir -p ./tmp
export TMPDIR=$(pwd)/tmp

# Start the Celery beat
echo "Starting Celery beat..."
celery -A tasks beat --loglevel=info