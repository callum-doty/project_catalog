# src/catalog/tasks/analysis_utils.py
import logging
from sqlalchemy.orm import Session
from flask import current_app

logger = logging.getLogger(__name__)


# Updated check_minimum_analysis in analysis_utils.py

def check_minimum_analysis(document_id: int) -> bool:
    """Check if document has minimum required analysis components"""
    try:
        # Import models here to avoid circular imports
        from src.catalog.models import LLMAnalysis, ExtractedText
        from src.catalog import db

        # Force a clean session to avoid stale data
        db.session.close()

        # Explicitly use separate queries with commit between checks
        llm_analysis = LLMAnalysis.query.filter_by(
            document_id=document_id).first()
        has_llm_analysis = llm_analysis is not None

        extracted_text = ExtractedText.query.filter_by(
            document_id=document_id).first()
        has_extracted_text = extracted_text is not None

        logger.info(
            f"Minimum analysis check: LLM Analysis: {has_llm_analysis}, Extracted Text: {has_extracted_text}")

        # Log more detailed info about the components if they exist
        if llm_analysis:
            logger.info(f"Found LLM analysis with ID {llm_analysis.id}")
            logger.info(
                f"LLM analysis summary: {llm_analysis.summary_description}")
        else:
            logger.warning(
                f"No LLM analysis found for document ID {document_id}")

        if extracted_text:
            logger.info(f"Found extracted text with ID {extracted_text.id}")
            logger.info(
                f"Extracted text content length: {len(extracted_text.text_content or '')}")
        else:
            logger.warning(
                f"No extracted text found for document ID {document_id}")

        # Consider document analyzable if it has at least one of these components
        return has_llm_analysis or has_extracted_text

    except Exception as e:
        logger.error(
            f"Error checking minimum analysis: {str(e)}", exc_info=True)
        return False
