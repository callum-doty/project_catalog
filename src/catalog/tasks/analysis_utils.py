# src/catalog/tasks/analysis_utils.py
import logging
from sqlalchemy.orm import Session
from flask import current_app

logger = logging.getLogger(__name__)


def check_minimum_analysis(document_id: int) -> bool:
    """Check if document has minimum required analysis components"""
    try:
        # Import models here to avoid circular imports
        from src.catalog.models import LLMAnalysis, ExtractedText
        from src.catalog import db

        # Document must have at least one of these to be considered analyzed
        has_llm_analysis = LLMAnalysis.query.filter_by(
            document_id=document_id).first() is not None
        has_extracted_text = ExtractedText.query.filter_by(
            document_id=document_id).first() is not None

        logger.info(
            f"Minimum analysis check: LLM Analysis: {has_llm_analysis}, Extracted Text: {has_extracted_text}")

        # Log all analysis components for document
        logger.info(f"Looking up LLM analysis for document ID {document_id}")
        llm_analysis = LLMAnalysis.query.filter_by(
            document_id=document_id).first()
        if llm_analysis:
            logger.info(f"Found LLM analysis with ID {llm_analysis.id}")
            logger.info(
                f"LLM analysis summary: {llm_analysis.summary_description}")
        else:
            logger.warning(
                f"No LLM analysis found for document ID {document_id}")

        logger.info(f"Looking up extracted text for document ID {document_id}")
        extracted_text = ExtractedText.query.filter_by(
            document_id=document_id).first()
        if extracted_text:
            logger.info(f"Found extracted text with ID {extracted_text.id}")
            logger.info(
                f"Extracted text content length: {len(extracted_text.text_content or '')}")
        else:
            logger.warning(
                f"No extracted text found for document ID {document_id}")

        # Consider document analyzable if it has basic metadata and text
        return has_llm_analysis or has_extracted_text
    except Exception as e:
        logger.error(
            f"Error checking minimum analysis: {str(e)}", exc_info=True)
        return False
