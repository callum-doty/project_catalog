# tasks/recovery_tasks.py

from .celery_app import celery_app, logger, TASK_STATUSES
from app.models.models import Document, LLMAnalysis, DesignElement, Classification, ExtractedText, LLMKeyword, Entity, CommunicationFocus
from app.extensions import db
from app.services.llm_service import LLMService
from app.services.llm_parser import LLMResponseParser
from app.services.storage_service import MinIOStorage
from datetime import datetime
import json


@celery_app.task(name='tasks.reprocess_document', bind=True)
def reprocess_document(self, filename: str, minio_path: str, document_id: int):
    """Reprocess a failed or stuck document"""
    logger.info(f"Starting reprocessing for document: {filename} (ID: {document_id})")
    
    # Import Flask app here to avoid circular import
    from app import create_app
    app = create_app()
    
    with app.app_context():
        doc = Document.query.get(document_id)
        
        if not doc:
            logger.error(f"Document not found: {document_id}")
            return False
            
        doc.status = TASK_STATUSES['PROCESSING']
        db.session.commit()
        
        # Remove any existing analysis data
        try:
            # Delete associated records in other tables - updated for new models
            LLMKeyword.query.join(LLMAnalysis).filter(LLMAnalysis.document_id == document_id).delete(synchronize_session=False)
            LLMAnalysis.query.filter_by(document_id=document_id).delete()
            DesignElement.query.filter_by(document_id=document_id).delete()
            Classification.query.filter_by(document_id=document_id).delete()
            ExtractedText.query.filter_by(document_id=document_id).delete()
            Entity.query.filter_by(document_id=document_id).delete()  # NEW
            CommunicationFocus.query.filter_by(document_id=document_id).delete()  # NEW
            
            db.session.commit()
            logger.info(f"Cleared previous analysis data for document: {document_id}")
        except Exception as e:
            logger.error(f"Error clearing previous analysis: {str(e)}")
            db.session.rollback()

        try:
            logger.info(f"Starting analysis for document: {filename}")
            
            # Initialize LLM service and analyze
            llm_service = LLMService()
            response = llm_service.analyze_document(filename)
            
            # Log the raw LLM response for debugging
            logger.info(f"Received LLM response, parsing results...")
            
            # Use updated store_analysis_results function
            from tasks.document_tasks import store_analysis_results
            store_analysis_results(document_id, response)
            
            # Update status and commit
            doc.status = TASK_STATUSES['COMPLETED']
            db.session.commit()
            logger.info(f"Reprocessing completed successfully")

            return True

        except Exception as e:
            logger.error(f"Document reprocessing failed: {str(e)}", exc_info=True)
            doc.status = TASK_STATUSES['FAILED']
            db.session.commit()
            raise