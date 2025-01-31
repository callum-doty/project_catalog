import os
from datetime import datetime
from celery import Task
from .celery_app import celery_app, handle_task_failure, logger, TASK_STATUSES
from app.services.analysis_prompt import get_analysis_prompt

from app.services.storage_service import MinIOStorage
from app.services.llm_service import LLMService
from app.models.models import (
    Document, BatchJob, LLMAnalysis, ExtractedText,
    DesignElement, Classification, LLMKeyword
)
from app.models import db
import json
from PIL import Image
import pytesseract
from pdf2image import convert_from_path

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

@celery_app.task(bind=True, base=DocumentProcessor)
@handle_task_failure
def process_document(self, filename: str, minio_path: str, document_id: int):
    """Process uploaded document through the pipeline"""
    doc = Document.query.get(document_id)
    doc.status = TASK_STATUSES['PROCESSING']
    db.session.commit()

    try:
        # Download file from MinIO
        temp_path = f"/tmp/{filename}"
        self.storage.download_file(filename, temp_path)

        # Extract text based on file type
        file_extension = filename.lower().split('.')[-1]
        if file_extension == 'pdf':
            extracted_text = extract_text_from_pdf(temp_path)
        else:
            extracted_text = extract_text_from_image(temp_path)

        # Store extracted text
        text_entry = ExtractedText(
            document_id=document_id,
            text_content=extracted_text,
            confidence=0.9,  # You might want to adjust this
            extraction_date=datetime.utcnow()
        )
        db.session.add(text_entry)

        # Get LLM analysis
        analysis_result = analyze_document.delay(filename, extracted_text, document_id)
        analysis_result.get()  # Wait for analysis to complete

        # Update document status
        doc.status = TASK_STATUSES['COMPLETED']
        db.session.commit()

    finally:
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)

def extract_text_from_pdf(filepath: str) -> str:
    """Extract text from PDF using pdf2image and pytesseract"""
    try:
        pages = convert_from_path(filepath)
        text = []
        for page in pages:
            text.append(pytesseract.image_to_string(page))
        return "\n".join(text)
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

@celery_app.task
@handle_task_failure
def analyze_document(filename: str, extracted_text: str, document_id: int):
    """Analyze document using Claude API"""
    llm_service = LLMService()
    
    try:
        # Get analysis from Claude
        analysis_prompt = get_analysis_prompt(filename)
        response = llm_service.analyze_text(extracted_text, analysis_prompt)
        analysis_data = json.loads(response)

        # Store LLM Analysis
        llm_analysis = LLMAnalysis(
            document_id=document_id,
            summary_description=analysis_data['document_analysis']['summary'],
            content_analysis=json.dumps(analysis_data['document_analysis']),
            confidence_score=analysis_data['document_analysis']['confidence_score'],
            analysis_date=datetime.utcnow(),
            model_version='claude-3'
        )
        db.session.add(llm_analysis)

        # Store Design Elements
        design = analysis_data['design_elements']
        design_element = DesignElement(
            documents_id=document_id,
            color_scheme=json.dumps(design['color_scheme']),
            theme=design['theme'],
            mail_piece_type=design['mail_piece_type'],
            geographic_location=design['geographic_location'],
            target_audience=design['target_audience'],
            campaign_name=design['campaign_name'],
            confidence=int(design['confidence'] * 100),
            created_date=datetime.utcnow()
        )
        db.session.add(design_element)

        # Store Classification
        classification = Classification(
            document_id=document_id,
            category=analysis_data['classification']['category'],
            confidence=int(analysis_data['classification']['confidence'] * 100),
            classification_date=datetime.utcnow()
        )
        db.session.add(classification)

        # Store Keywords
        for keyword_data in analysis_data['keywords']:
            keyword = LLMKeyword(
                llm_analysis_id=llm_analysis.id,
                keyword=keyword_data['text'],
                category=keyword_data['category'],
                relevance_score=int(keyword_data['confidence'] * 100)
            )
            db.session.add(keyword)

        db.session.commit()

    except Exception as e:
        logger.error(f"Document analysis failed: {str(e)}")
        db.session.rollback()
        raise