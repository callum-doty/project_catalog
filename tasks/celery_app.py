# tasks/celery_app.py

# First, import Redis fix if available
try:
    import fix_redis
except ImportError:
    pass

from celery import Celery
from celery.utils.log import get_task_logger
from celery.schedules import crontab
import functools
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = get_task_logger(__name__)

# Verify Redis URLs before proceeding
broker_url = os.environ.get('CELERY_BROKER_URL') or os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
result_backend = os.environ.get('CELERY_RESULT_BACKEND') or os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'

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

# Task status tracking
TASK_STATUSES = {
    'PENDING': 'PENDING',
    'PROCESSING': 'PROCESSING',
    'COMPLETED': 'COMPLETED',
    'FAILED': 'FAILED'
}

# Configure task routing
celery_app.conf.task_routes = {
    'tasks.process_document': {'queue': 'document_processing'},
    'tasks.analyze_document': {'queue': 'analysis'},
    'tasks.sync_dropbox': {'queue': 'document_processing'},
}

# Error handling decorator
def handle_task_failure(task_func):
    @functools.wraps(task_func)
    def wrapper(*args, **kwargs):
        try:
            return task_func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Task failed: {str(e)}", exc_info=True)
            # Update document status to failed if document_id is provided
            try:
                from app.models import Document, db
                document_id = kwargs.get('document_id')
                if document_id:
                    doc = Document.query.get(document_id)
                    if doc:
                        doc.status = TASK_STATUSES['FAILED']
                        db.session.commit()
            except Exception as db_error:
                logger.error(f"Failed to update document status: {str(db_error)}")
            raise
    return wrapper

# Simplified beat schedule for testing
celery_app.conf.beat_schedule = {
    'sync-dropbox-every-10-minutes': {
        'task': 'tasks.sync_dropbox',
        'schedule': crontab(minute='*/10'),  # Run every 10 minutes
    },
}

# Verify Redis connection on module import
try:
    with celery_app.connection_or_acquire() as conn:
        logger.info("Successfully connected to Redis")
except Exception as e:
    logger.error(f"Failed to connect to Redis: {str(e)}")