# tasks/celery_app.py

from celery import Celery
from celery.utils.log import get_task_logger
from celery.schedules import crontab
import functools

# Initialize Celery
celery_app = Celery('tasks', broker='redis://redis:6379/0')

# Configure Celery
celery_app.conf.update(
    result_backend='redis://redis:6379/0',
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

logger = get_task_logger(__name__)

# Task status tracking
TASK_STATUSES = {
    'PENDING': 'PENDING',
    'PROCESSING': 'PROCESSING',
    'COMPLETED': 'COMPLETED',
    'FAILED': 'FAILED'
}

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

# Beat schedule for Dropbox sync
celery_app.conf.beat_schedule = {
    'sync-dropbox-every-5-minutes': {
        'task': 'tasks.sync_dropbox',
        'schedule': crontab(minute='*/5'),  # Run every 5 minutes
    },
}