# tasks/document_tasks.py

import os
import time
import json
from celery import Task
from .celery_app import celery_app, logger
from .utils import TASK_STATUSES, handle_task_failure
from app.models.models import Document, LLMAnalysis, LLMKeyword, Classification, DesignElement, ExtractedText, DropboxSync  
from datetime import datetime, timedelta
from app.services.storage_service import MinIOStorage
from app.extensions import db

class DocumentProcessor(Task):
    abstract = True
    _storage = None
    _llm_service = None
    
    @property
    def storage(self):
        if self._storage is None:
            from app.services.storage_service import MinIOStorage
            self._storage = MinIOStorage()
        return self._storage
    
    @property
    def llm_service(self):
        if self._llm_service is None:
            from app.services.llm_service import LLMService
            self._llm_service = LLMService()
        return self._llm_service
    
    def download_temp_file(self, filename):
        """Download file to temp location for processing"""
        try:
            temp_path = f"/tmp/{filename}"
            self.storage.download_file(filename, temp_path)
            return temp_path
        except Exception as e:
            logger.error(f"Error downloading file: {str(e)}")
            return None


@celery_app.task(name='tasks.list_tasks')
def list_tasks():
    """List all registered tasks"""
    logger.info("Listing all registered Celery tasks:")
    for task_name in sorted(celery_app.tasks.keys()):
        logger.info(f"- {task_name}")
    return list(celery_app.tasks.keys())

@celery_app.task(bind=True, name='tasks.test_document_processing')
def test_document_processing(self, document_id):
    """Simplified document processing to test Celery execution"""
    logger.info(f"=== TESTING DOCUMENT PROCESSING === Task ID: {self.request.id}")
    logger.info(f"Document ID: {document_id}")
    
    try:
        # Import Flask app
        from app import create_app
        app = create_app()
        
        with app.app_context():
            # Update document status
            from app.models.models import Document
            from tasks.celery_app import TASK_STATUSES
            from app.extensions import db
            
            doc = Document.query.get(document_id)
            if doc:
                logger.info(f"Found document: {doc.filename}")
                doc.status = TASK_STATUSES['COMPLETED']
                db.session.commit()
                logger.info("Document status updated to COMPLETED")
                return True
            else:
                logger.error(f"Document with ID {document_id} not found")
                return False
    except Exception as e:
        logger.error(f"Error in test processing: {str(e)}", exc_info=True)
        raise


@celery_app.task(bind=True, name='tasks.process_document')
def process_document(self, filename, minio_path, document_id):
    """Process document through the pipeline"""
    logger.info(f"=== STARTING DOCUMENT PROCESSING ===")
    logger.info(f"Task ID: {self.request.id}")
    logger.info(f"Processing document: {filename}")
    logger.info(f"MinIO path: {minio_path}")
    logger.info(f"Document ID: {document_id}")
    
    # Import Flask app here to avoid circular import
    from app import create_app
    app = create_app()
    
    with app.app_context():
        doc = Document.query.get(document_id)
        if not doc:
            logger.error(f"Document with ID {document_id} not found")
            return False
            
        doc.status = TASK_STATUSES['PROCESSING']
        db.session.commit()
        logger.info(f"Updated document status to PROCESSING")
        
        try:
            logger.info(f"Starting analysis for document: {filename}")
            
            # Initialize LLM service and analyze
            from app.services.llm_service import LLMService
            llm_service = LLMService()
            
            logger.info(f"Calling Claude API for document analysis")
            response = llm_service.analyze_document(filename)
            
            # Log the raw LLM response for debugging
            logger.info(f"Received LLM response, parsing results...")

            store_analysis_results(document_id, response)
            
            # Parse results
            from app.services.llm_parser import LLMResponseParser
            parser = LLMResponseParser()
            
            
            # Update status and commit
            doc.status = TASK_STATUSES['COMPLETED']
            db.session.commit()
            logger.info(f"Analysis completed successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"Document processing failed: {str(e)}", exc_info=True)
            doc.status = TASK_STATUSES['FAILED']
            db.session.commit()
            raise

def store_analysis_results(document_id: int, response: dict):
    """Store analysis results in database"""
    from app.models.models import Document, LLMAnalysis, ExtractedText, LLMKeyword
    from app.extensions import db
    
    try:
        # Store LLM Analysis
        analysis_data = response.get('document_analysis', {})
        llm_analysis = LLMAnalysis(
            document_id=document_id,
            summary_description=analysis_data.get('summary', ''),
            visual_analysis=response.get('design_elements', {}).get('theme', ''),
            content_analysis=json.dumps(response),
            confidence_score=float(analysis_data.get('confidence_score', 0.9)),
            analysis_date=datetime.utcnow(),
            model_version='claude-3-opus-20240229'  # Updated to Claude 3 Opus
        )
        db.session.add(llm_analysis)
        db.session.flush()  # Get the ID for keywords

        # Store Keywords
        keywords_data = response.get('keywords', [])
        for keyword in keywords_data[:5]:  # Limit to 5 keywords
            keyword_entry = LLMKeyword(
                llm_analysis_id=llm_analysis.id,
                keyword=keyword.get('text', ''),
                category=keyword.get('category', ''),
                relevance_score=int(float(keyword.get('confidence', 0.9)) * 100)
            )
            db.session.add(keyword_entry)

        # Store Extracted Text
        text_data = response.get('extracted_text', {})
        text_entry = ExtractedText(
            document_id=document_id,
            text_content=f"{text_data.get('main_message', '')}\n\n{text_data.get('supporting_text', '')}",
            confidence=float(text_data.get('confidence', 0.9)),
            extraction_date=datetime.utcnow()
        )
        db.session.add(text_entry)
        
        db.session.commit()
        logger.info(f"Successfully stored analysis results for document {document_id}")
        
    except Exception as e:
        logger.error(f"Error storing analysis results: {str(e)}")
        db.session.rollback()
        raise



@celery_app.task(name='tasks.recover_pending_documents')
def recover_pending_documents():
    """Identify and recover documents stuck in PENDING state"""
    from app import create_app
    app = create_app()
    
    with app.app_context():
        # Get documents stuck in PENDING state for more than 1 hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        stuck_documents = Document.query.filter_by(status='PENDING') \
            .filter(Document.upload_date < one_hour_ago) \
            .all()
        
        logger.info(f"Found {len(stuck_documents)} documents stuck in PENDING state")
        
        storage = MinIOStorage()  # Initialize storage service
        
        for doc in stuck_documents:
            try:
                # Check if document exists in MinIO
                minio_path = f"{storage.bucket}/{doc.filename}"
                try:
                    storage.client.stat_object(storage.bucket, doc.filename)
                    file_exists = True
                except:
                    file_exists = False
                
                if file_exists:
                    # Reprocess the document
                    logger.info(f"Reprocessing stuck document: {doc.filename}")
                    process_document.delay(doc.filename, minio_path, doc.id)
                else:
                    # Mark as failed if file doesn't exist
                    logger.error(f"Document file not found in storage: {doc.filename}")
                    doc.status = 'FAILED'
                    db.session.commit()
            except Exception as e:
                logger.error(f"Error recovering document {doc.id}: {str(e)}")
        
        return f"Processed {len(stuck_documents)} stuck documents"