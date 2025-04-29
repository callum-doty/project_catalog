# tasks/utils.py
import functools
import logging
from src.catalog.constants import DOCUMENT_STATUSES

logger = logging.getLogger(__name__)


def handle_task_failure(task_func):
    @functools.wraps(task_func)
    def wrapper(*args, **kwargs):
        try:
            return task_func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Task failed: {str(e)}", exc_info=True)
            # Update document status to failed if document_id is provided
            try:
                from catalog.models import Document, db
                document_id = kwargs.get('document_id')
                if document_id:
                    doc = Document.query.get(document_id)
                    if doc:
                        doc.status = DOCUMENT_STATUSES['FAILED']
                        db.session.commit()
            except Exception as db_error:
                logger.error(
                    f"Failed to update document status: {str(db_error)}")
            raise
    return wrapper
