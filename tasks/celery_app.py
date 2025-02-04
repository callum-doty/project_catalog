# tasks/celery_app.py

from celery import Celery
from celery.utils.log import get_task_logger
from config.settings import settings

logger = get_task_logger(__name__)

# Initialize Celery
celery_app = Celery('tasks')

# Configure Celery
celery_app.conf.update(
    broker_url=settings.broker_url,
    result_backend=settings.result_backend,
    task_serializer=settings.task_serializer,
    result_serializer=settings.result_serializer,
    accept_content=settings.accept_content,
    timezone=settings.timezone,
    enable_utc=settings.enable_utc,
    task_routes=settings.task_routes,
    imports=['tasks.document_tasks']
)

# Task status tracking
TASK_STATUSES = {
    'PENDING': 'PENDING',
    'PROCESSING': 'PROCESSING',
    'COMPLETED': 'COMPLETED',
    'FAILED': 'FAILED'
}

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