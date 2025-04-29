# tasks/recovery_tasks.py

from .celery_app import celery_app, logger
from src.catalog.models import Document
from src.catalog import db
from src.catalog.constants import DOCUMENT_STATUSES


@celery_app.task(name='tasks.reprocess_document', bind=True)
def reprocess_document(self, filename: str, minio_path: str, document_id: int):
    """Reprocess a document that failed or is stuck"""
    logger.info(
        f"Starting reprocessing for document: {filename} (ID: {document_id})")

    # Import Flask app
    from catalog import create_app
    app = create_app()

    with app.app_context():
        doc = Document.query.get(document_id)

        if not doc:
            logger.error(f"Document not found: {document_id}")
            return False

        # Update status to PENDING
        doc.status = DOCUMENT_STATUSES['PENDING']  # Use imported constant
        db.session.commit()

        # Call the regular processing task
        from tasks.document_tasks import process_document
        process_document.delay(filename, minio_path, document_id)

        logger.info(f"Queued document {document_id} for reprocessing")
        return True
