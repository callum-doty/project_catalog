import os
from datetime import datetime
import json
from celery import Task
from .celery_app import celery_app, logger, TASK_STATUSES
from app.services.analysis_prompt import get_analysis_prompt
from app.services.storage_service import MinIOStorage
from app.services.llm_service import LLMService
from app.models.models import Document, BatchJob, LLMAnalysis, ExtractedText, DesignElement, Classification, LLMKeyword
from app.extensions import db
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
from app.services.llm_parser import LLMResponseParser
from flask import current_app

class DocumentProcessor(Task):
    abstract = True
    _storage = None
    _llm_service = None
    
    @property
    def storage(self):
        if self._storage is None:
            self._storage = MinIOStorage()
        return self._storage
    
    @property
    def llm_service(self):
        if self._llm_service is None:
            self._llm_service = LLMService()
        return self._llm_service

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        document_id = kwargs.get('document_id')
        if document_id:
            doc = Document.query.get(document_id)
            if doc:
                doc.status = TASK_STATUSES['FAILED']
                db.session.commit()
        logger.error(f"Task {task_id} failed: {str(exc)}", exc_info=einfo)

    def extract_text_from_pdf(filepath: str) -> str:
        """Extract text from PDF using pdf2image and pytesseract"""
        try:
            images = convert_from_path(filepath)
            text_parts = []
            for i, image in enumerate(images):
                text = pytesseract.image_to_string(image)
                text_parts.append(text)
            return "\n\n".join(text_parts)
        except Exception as e:
            logger.error(f"PDF text extraction failed: {str(e)}")
            raise

    def extract_text_from_image(filepath: str) -> str:
        """Extract text from image using pytesseract"""
        try:
            image = Image.open(filepath)
            return pytesseract.image_to_string(image)
        except Exception as e:
            logger.error(f"Image text extraction failed: {str(e)}")
            raise

@celery_app.task(bind=True, base=DocumentProcessor)
def process_document(self, filename: str, minio_path: str, document_id: int):
    """Process document through the pipeline"""
    # Import Flask app here to avoid circular import
    from app import create_app
    app = create_app()
    
    with app.app_context():
        doc = Document.query.get(document_id)
        doc.status = TASK_STATUSES['PROCESSING']
        db.session.commit()

        try:
            logger.info(f"Starting analysis for document: {filename}")
            
            # Initialize LLM service and analyze
            llm_service = LLMService()
            response = llm_service.analyze_document(filename)
            
            # Log the raw LLM response for debugging
            logger.info(f"Raw LLM response for {filename}: {json.dumps(response)}")
            
            logger.info(f"Received LLM response, parsing results...")
            
            # Parse results
            parser = LLMResponseParser()
            
            # Store LLM Analysis
            try:
                llm_analysis_data = parser.parse_llm_analysis(response)
                llm_analysis = LLMAnalysis(
                    document_id=document_id,
                    **llm_analysis_data
                )
                db.session.add(llm_analysis)
                db.session.flush()
                logger.info(f"Stored LLM analysis")
            except Exception as e:
                logger.error(f"Failed to store LLM analysis: {str(e)}")
                raise

            # Store Design Elements
            try:
                design_data = parser.parse_design_elements(response)
                design_element = DesignElement(
                    document_id=document_id,
                    **design_data
                )
                db.session.add(design_element)
                logger.info(f"Stored design elements")
            except Exception as e:
                logger.error(f"Failed to store design elements: {str(e)}")
                raise

            # Store Classification
            try:
                classification_data = parser.parse_classification(response)
                classification = Classification(
                    document_id=document_id,
                    **classification_data
                )
                db.session.add(classification)
                logger.info(f"Stored classification")
            except Exception as e:
                logger.error(f"Failed to store classification: {str(e)}")
                raise

            # Store Extracted Text
            try:
                text_data = response.get('extracted_text', {})
                main_message = text_data.get('main_message', '')
                supporting_text = text_data.get('supporting_text', '')
                
                # Handle cases where messages might be lists
                if isinstance(main_message, list):
                    main_message = ' '.join(str(msg) for msg in main_message)
                if isinstance(supporting_text, list):
                    supporting_text = ' '.join(str(msg) for msg in supporting_text)
                
                text_entry = ExtractedText(
                    document_id=document_id,
                    text_content=f"{main_message}\n\n{supporting_text}",
                    confidence=float(text_data.get('confidence', 0.9)),
                    extraction_date=datetime.utcnow()
                )
                db.session.add(text_entry)
                logger.info(f"Stored extracted text")
            except Exception as e:
                logger.error(f"Failed to store extracted text: {str(e)}")
                raise

            # Store Keywords
            try:
                keywords_data = parser.parse_keywords(response)
                if keywords_data:
                    for keyword_data in keywords_data:
                        keyword = LLMKeyword(
                            llm_analysis_id=llm_analysis.id,
                            **keyword_data
                        )
                        db.session.add(keyword)
                    logger.info(f"Stored {len(keywords_data)} keywords")
                else:
                    logger.warning("No keywords found to store")
            except Exception as e:
                logger.error(f"Failed to store keywords: {str(e)}")
                raise

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