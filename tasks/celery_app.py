# tasks/celery_app.py

from celery import Celery
from celery.utils.log import get_task_logger
from datetime import datetime

# Initialize Celery
celery_app = Celery('tasks')

# Configure Celery
celery_app.conf.update(
    broker_url='redis://redis:6379/0',
    result_backend='redis://redis:6379/0',
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    imports=['tasks.document_tasks'],
    task_routes={
        'tasks.document_tasks.process_document': {'queue': 'document_processing'},
        'tasks.document_tasks.analyze_document': {'queue': 'analysis'}
    }
)

logger = get_task_logger(__name__)

# Task status tracking
TASK_STATUSES = {
    'PENDING': 'PENDING',
    'PROCESSING': 'PROCESSING',
    'COMPLETED': 'COMPLETED',
    'FAILED': 'FAILED'
}

# Error handling decorator
def handle_task_failure(task_func):
    def wrapper(*args, **kwargs):
        try:
            return task_func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Task failed: {str(e)}", exc_info=True)
            # Update document status to failed if possible
            from app.models import Document, db
            document_id = kwargs.get('document_id')
            if document_id:
                doc = Document.query.get(document_id)
                if doc:
                    doc.status = TASK_STATUSES['FAILED']
                    db.session.commit()
            raise
    return wrapper