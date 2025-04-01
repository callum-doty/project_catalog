# tasks/celery_app.py

# First, import Redis fix if available
try:
    import fix_redis
except ImportError:
    pass

import os
import sys
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    # Try to import celery
    from celery import Celery
    logger.info("Successfully imported Celery")
except ImportError as e:
    logger.error(f"Failed to import Celery: {str(e)}")
    raise

# Verify Redis URLs before proceeding
broker_url = os.environ.get('CELERY_BROKER_URL') or os.environ.get('REDIS_URL') or 'redis://redis:6379/0'
result_backend = os.environ.get('CELERY_RESULT_BACKEND') or os.environ.get('REDIS_URL') or 'redis://redis:6379/0'

# Log Redis configuration
safe_broker = broker_url.replace('redis://', 'redis://****:****@')
logger.info(f"Initializing Celery with broker: {safe_broker}")

# Initialize Celery with explicit broker URL
celery_app = Celery('tasks', broker=broker_url)

# Configure Celery
celery_app.conf.update(
    result_backend=result_backend,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

# Task status tracking - add this back
TASK_STATUSES = {
    'PENDING': 'PENDING',
    'PROCESSING': 'PROCESSING',
    'COMPLETED': 'COMPLETED',
    'FAILED': 'FAILED'
}

# Configure task routing
celery_app.conf.task_routes = {
    'tasks.process_document': {'queue': 'document_processing'},
    'tasks.test_document_processing': {'queue': 'document_processing'},
    'tasks.analyze_document': {'queue': 'analysis'},
    'tasks.sync_dropbox': {'queue': 'document_processing'}, 
}

# Verify Redis connection on module import
try:
    with celery_app.connection_or_acquire() as conn:
        logger.info("Successfully connected to Redis")
except Exception as e:
    logger.error(f"Failed to connect to Redis: {str(e)}")