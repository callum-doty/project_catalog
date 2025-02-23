# tasks/document_tasks.py

import os
from datetime import datetime
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

@celery_app.task(bind=True, base=DocumentProcessor)
@handle_task_failure
def process_document(self, filename: str, minio_path: str, document_id: int):
    """Process document through the pipeline"""
    # Import Flask app here to avoid circular imports
    from app import create_app
    app = create_app()
    
    with app.app_context():
        from app.models.models import Document, LLMAnalysis, ExtractedText
        from app.extensions import db
        
        doc = Document.query.get(document_id)
        doc.status = TASK_STATUSES['PROCESSING']
        db.session.commit()

        try:
            logger.info(f"Starting analysis for document: {filename}")
            
            # Initialize LLM service and analyze
            response = self.llm_service.analyze_document(filename)
            
            # Store results
            store_analysis_results(document_id, response)
            
            # Update status
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
            model_version='claude-2'
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