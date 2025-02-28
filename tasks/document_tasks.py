# tasks/document_tasks.py

import os
from datetime import datetime
import time
import json
from celery import Task
from .celery_app import celery_app, logger
from .utils import TASK_STATUSES, handle_task_failure

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

@celery_app.task(bind=True, base=DocumentProcessor)
@handle_task_failure
def process_document(self, filename: str, minio_path: str, document_id: int):
    """Process document through the pipeline and track processing time"""
    # Import Flask app here to avoid circular imports
    from app import create_app
    app = create_app()
    
    with app.app_context():
        from app.models.models import Document, LLMAnalysis, ExtractedText
        from app.extensions import db
        
        doc = Document.query.get(document_id)
        doc.status = TASK_STATUSES['PROCESSING']
        db.session.commit()

        # Start timing the processing
        start_time = time.time()

        try:
            logger.info(f"Starting analysis for document: {filename}")
            
            # Download the file for potential image analysis
            temp_path = None
            image_path = None
            
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                # If it's an image file, use it directly for image analysis
                image_path = self.download_temp_file(filename)
            elif filename.lower().endswith('.pdf'):
                # For PDFs, download for potential text extraction
                temp_path = self.download_temp_file(filename)
                # You could extract the first page as an image here if needed
            
            # Initialize LLM service and analyze
            try:
                # Include image path if available
                if image_path:
                    response = self.llm_service.analyze_document(filename, image_path=image_path)
                else:
                    response = self.llm_service.analyze_document(filename)
                
                # Store results
                store_analysis_results(document_id, response)
                
                # Calculate processing time
                processing_time = time.time() - start_time
                
                # Update document with processing time and complete status
                doc.processing_time = processing_time
                doc.status = TASK_STATUSES['COMPLETED']
                db.session.commit()
                
                logger.info(f"Analysis completed successfully in {processing_time:.2f} seconds")
                
            finally:
                # Clean up temporary files
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
                if image_path and os.path.exists(image_path) and image_path != temp_path:
                    os.remove(image_path)

            return True

        except Exception as e:
            # Still record the processing time even for failures
            processing_time = time.time() - start_time
            doc.processing_time = processing_time
            doc.status = TASK_STATUSES['FAILED']
            db.session.commit()
            
            logger.error(f"Document processing failed after {processing_time:.2f} seconds: {str(e)}", exc_info=True)
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