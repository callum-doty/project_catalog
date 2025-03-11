# tasks/recovery_tasks.py

from .celery_app import celery_app, logger, TASK_STATUSES
from app.models.models import Document, LLMAnalysis, DesignElement, Classification, ExtractedText, LLMKeyword
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
            # Delete associated records in other tables
            LLMKeyword.query.join(LLMAnalysis).filter(LLMAnalysis.document_id == document_id).delete(synchronize_session=False)
            LLMAnalysis.query.filter_by(document_id=document_id).delete()
            DesignElement.query.filter_by(document_id=document_id).delete()
            Classification.query.filter_by(document_id=document_id).delete()
            ExtractedText.query.filter_by(document_id=document_id).delete()
            
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
            logger.info(f"Reprocessing completed successfully")

            return True

        except Exception as e:
            logger.error(f"Document reprocessing failed: {str(e)}", exc_info=True)
            doc.status = TASK_STATUSES['FAILED']
            db.session.commit()
            raise