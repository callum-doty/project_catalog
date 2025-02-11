# tasks/utils.py

import functools
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

# Task status tracking
TASK_STATUSES = {
    'PENDING': 'PENDING',
    'PROCESSING': 'PROCESSING',
    'COMPLETED': 'COMPLETED',
    'FAILED': 'FAILED'
}

def handle_task_failure(task_func):
    @functools.wraps(task_func)
    def wrapper(*args, **kwargs):
        try:
            return task_func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Task failed: {str(e)}", exc_info=True)
            # Update document status to failed if document_id is provided
            from app.models import Document, db
            document_id = kwargs.get('document_id')
            if document_id:
                doc = Document.query.get(document_id)
                if doc:
                    doc.status = TASK_STATUSES['FAILED']
                    db.session.commit()
            raise
    return wrapper