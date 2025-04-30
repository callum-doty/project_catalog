#!/usr/bin/env python
"""
Diagnostic script for document processing issues.
This script checks documents that failed processing and attempts to repair them.
"""
from sqlalchemy import text
import os
import sys
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("document_repair")


#!/usr/bin/env python
"""
Simple document status checker for debugging database issues.
"""

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("document_repair")


def init_app():
    """Initialize Flask app in a way that works for local debugging"""
    from src.catalog import create_app
    app = create_app()
    return app


def check_document(document_id):
    """Focus only on checking the document and its database records"""
    try:
        from src.catalog.models import Document, LLMAnalysis, ExtractedText
        from src.catalog import db

        logger.info(f"Checking document ID: {document_id}")

        # Test basic database connection with proper text construct
        try:
            result = db.session.execute(text("SELECT 1")).scalar()
            logger.info(f"Database connection check: {result}")
        except Exception as e:
            logger.error(f"Database connection failed: {str(e)}")
            return

        # Get document and component records
        document = Document.query.get(document_id)
        if not document:
            logger.error(f"Document {document_id} not found")
            return

        logger.info(
            f"Document found: {document.filename} (Status: {document.status})")

        # Check for related records directly
        llm_analysis = LLMAnalysis.query.filter_by(
            document_id=document_id).first()
        logger.info(f"LLM Analysis: {'FOUND' if llm_analysis else 'MISSING'}")

        extracted_text = ExtractedText.query.filter_by(
            document_id=document_id).first()
        logger.info(
            f"Extracted Text: {'FOUND' if extracted_text else 'MISSING'}")

        # Manually check minimum analysis
        has_minimum = bool(llm_analysis or extracted_text)
        logger.info(f"Has minimum required analysis: {has_minimum}")

    except Exception as e:
        logger.error(f"Error: {str(e)}")


def main():
    """Main function"""
    if len(sys.argv) < 2:
        logger.error("Please provide a document ID")
        print("Usage: python simple_document_check.py <document_id>")
        return

    try:
        document_id = int(sys.argv[1])
    except ValueError:
        logger.error(f"Invalid document ID: {sys.argv[1]}")
        return

    app = init_app()
    with app.app_context():
        check_document(document_id)


if __name__ == "__main__":
    main()
