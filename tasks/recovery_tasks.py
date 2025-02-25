# tasks/recovery_tasks.py

import time
from celery import shared_task
from celery.utils.log import get_task_logger
from app.extensions import db
from app.models.models import Document
from app import create_app
from .document_tasks import process_document
from .utils import TASK_STATUSES
from .celery_app import celery_app

logger = get_task_logger(__name__)

@celery_app.task(name='tasks.reprocess_failed_documents')
def reprocess_failed_documents(delay_seconds=10, batch_size=5):
    """
    Reprocess documents that previously failed.
    
    Args:
        delay_seconds: Seconds to wait between processing each document to avoid rate limits
        batch_size: Number of documents to process in this run
    """
    app = create_app()
    
    with app.app_context():
        # Find documents with FAILED status
        failed_docs = Document.query.filter_by(status=TASK_STATUSES['FAILED']).limit(batch_size).all()
        
        if not failed_docs:
            logger.info("No failed documents found to reprocess")
            return "No failed documents found"
            
        logger.info(f"Found {len(failed_docs)} failed documents to reprocess")
        
        success_count = 0
        for doc in failed_docs:
            try:
                logger.info(f"Reprocessing document {doc.id}: {doc.filename}")
                
                # Update status to PENDING
                doc.status = TASK_STATUSES['PENDING']
                db.session.commit()
                
                # Construct the MinIO path
                minio_path = f"documents/{doc.filename}"
                
                # Schedule the document for processing
                process_document.delay(doc.filename, minio_path, doc.id)
                
                success_count += 1
                
                # Wait between documents to avoid rate limits
                if delay_seconds > 0 and success_count < len(failed_docs):
                    logger.info(f"Waiting {delay_seconds} seconds before next document...")
                    time.sleep(delay_seconds)
                    
            except Exception as e:
                logger.error(f"Error reprocessing document {doc.id}: {str(e)}")
                doc.status = TASK_STATUSES['FAILED']
                db.session.commit()
        
        return f"Reprocessed {success_count} out of {len(failed_docs)} failed documents"

@celery_app.task(name='tasks.reprocess_specific_document')
def reprocess_specific_document(document_id):
    """
    Reprocess a specific document by ID
    
    Args:
        document_id: The ID of the document to reprocess
    """
    app = create_app()
    
    with app.app_context():
        doc = Document.query.get(document_id)
        
        if not doc:
            logger.error(f"Document with ID {document_id} not found")
            return f"Document with ID {document_id} not found"
            
        try:
            logger.info(f"Reprocessing document {doc.id}: {doc.filename}")
            
            # Update status to PENDING
            doc.status = TASK_STATUSES['PENDING']
            db.session.commit()
            
            # Construct the MinIO path
            minio_path = f"documents/{doc.filename}"
            
            # Schedule the document for processing
            process_document.delay(doc.filename, minio_path, doc.id)
            
            return f"Document {document_id} ({doc.filename}) reprocessing started"
                
        except Exception as e:
            logger.error(f"Error reprocessing document {doc.id}: {str(e)}")
            doc.status = TASK_STATUSES['FAILED']
            db.session.commit()
            return f"Error reprocessing document {document_id}: {str(e)}"