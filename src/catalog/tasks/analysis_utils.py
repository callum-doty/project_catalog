import logging
from src.catalog.models import LLMAnalysis, ExtractedText

logger = logging.getLogger(__name__)


def check_minimum_analysis(document_id: int) -> bool:
    """Check if document has minimum required analysis components"""
    try:
        # Document must have at least one of these to be considered analyzed
        has_llm_analysis = LLMAnalysis.query.filter_by(
            document_id=document_id).first() is not None
        has_extracted_text = ExtractedText.query.filter_by(
            document_id=document_id).first() is not None

        logger.info(
            f"Minimum analysis check: LLM Analysis: {has_llm_analysis}, Extracted Text: {has_extracted_text}")

        # Consider document analyzable if it has basic metadata and text
        return has_llm_analysis or has_extracted_text
    except Exception as e:
        logger.error(f"Error checking minimum analysis: {str(e)}")
        return False
