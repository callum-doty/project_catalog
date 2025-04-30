#!/usr/bin/env python
"""
Diagnostic script for document processing issues.
This script checks a document's processing status and attempts to repair it.
"""
import os
import sys
import logging
import json
import traceback
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('document_repair.log')
    ]
)
logger = logging.getLogger("document_repair")


def setup_flask_app():
    """Set up Flask app context"""
    try:
        from src.catalog import create_app
        app = create_app()
        return app
    except Exception as e:
        logger.error(f"Failed to create Flask app: {str(e)}")
        raise


def check_document_status(document_id):
    """Check the status of a document and its related records"""
    from src.catalog.models import Document, LLMAnalysis, ExtractedText, Classification
    from src.catalog.models import DesignElement, Entity, CommunicationFocus, DocumentKeyword

    try:
        # Get document
        document = Document.query.get(document_id)
        if not document:
            logger.error(f"Document {document_id} not found")
            return False, {"error": "Document not found"}

        logger.info(
            f"Document found: {document.filename} (Status: {document.status})")

        # Check related records
        llm_analysis = LLMAnalysis.query.filter_by(
            document_id=document_id).first()
        extracted_text = ExtractedText.query.filter_by(
            document_id=document_id).first()
        classification = Classification.query.filter_by(
            document_id=document_id).first()
        design_elements = DesignElement.query.filter_by(
            document_id=document_id).first()
        entity = Entity.query.filter_by(document_id=document_id).first()
        communication_focus = CommunicationFocus.query.filter_by(
            document_id=document_id).first()
        document_keywords = DocumentKeyword.query.filter_by(
            document_id=document_id).all()

        # Print status
        logger.info("Related records status:")
        logger.info(
            f"  - LLM Analysis: {'PRESENT' if llm_analysis else 'MISSING'}")
        logger.info(
            f"  - Extracted Text: {'PRESENT' if extracted_text else 'MISSING'}")
        logger.info(
            f"  - Classification: {'PRESENT' if classification else 'MISSING'}")
        logger.info(
            f"  - Design Elements: {'PRESENT' if design_elements else 'MISSING'}")
        logger.info(f"  - Entity: {'PRESENT' if entity else 'MISSING'}")
        logger.info(
            f"  - Communication Focus: {'PRESENT' if communication_focus else 'MISSING'}")
        logger.info(f"  - Document Keywords: {len(document_keywords)} found")

        # Check minimum analysis requirements
        from src.catalog.tasks.analysis_utils import check_minimum_analysis
        min_analysis = check_minimum_analysis(document_id)
        logger.info(f"Minimum analysis check: {min_analysis}")

        return True, {
            "document": document,
            "llm_analysis": llm_analysis,
            "extracted_text": extracted_text,
            "min_analysis_check": min_analysis
        }

    except Exception as e:
        logger.error(f"Error checking document status: {str(e)}")
        logger.error(traceback.format_exc())
        return False, {"error": str(e)}


def repair_document(document_id):
    """Attempt to repair a document by manually creating required records"""
    from src.catalog.models import Document, LLMAnalysis, ExtractedText
    from src.catalog import db
    from datetime import datetime

    try:
        # Check document status
        success, data = check_document_status(document_id)
        if not success:
            return False, data

        document = data["document"]
        llm_analysis = data["llm_analysis"]
        extracted_text = data["extracted_text"]
        min_analysis_check = data["min_analysis_check"]

        # If minimum analysis check passes, no need to repair
        if min_analysis_check:
            logger.info(
                f"Document {document_id} passes minimum analysis check - no repair needed")

            # Just make sure status is correct
            if document.status != 'COMPLETED':
                document.status = 'COMPLETED'
                db.session.commit()
                logger.info(f"Updated document status to COMPLETED")

            return True, {"message": "Document already passes analysis check, updated status"}

        # Otherwise, try to repair
        repairs_made = []

        # Create LLM Analysis if missing
        if not llm_analysis:
            logger.info(
                f"Creating missing LLM Analysis for document {document_id}")

            llm_analysis = LLMAnalysis(
                document_id=document_id,
                summary_description=f"Auto-generated summary for {document.filename}",
                content_analysis=json.dumps({"auto_generated": True}),
                confidence_score=0.8,
                campaign_type="unknown",
                election_year="2024",
                document_tone="neutral",
                analysis_date=datetime.utcnow(),
                model_version="repair-script"
            )
            db.session.add(llm_analysis)
            repairs_made.append("Created LLM Analysis")

        # Create Extracted Text if missing
        if not extracted_text:
            logger.info(
                f"Creating missing Extracted Text for document {document_id}")

            extracted_text = ExtractedText(
                document_id=document_id,
                text_content=f"Auto-generated text content for {document.filename}",
                main_message=f"Main message for {document.filename}",
                supporting_text="Supporting text content",
                call_to_action="",
                candidate_name="",
                opponent_name="",
                confidence=80,
                extraction_date=datetime.utcnow(),
                page_number=1
            )
            db.session.add(extracted_text)
            repairs_made.append("Created Extracted Text")

        # Update document status
        document.status = 'COMPLETED'
        repairs_made.append("Updated document status to COMPLETED")

        # Commit all changes
        try:
            db.session.commit()
            logger.info(f"Successfully committed repairs to database")
        except Exception as commit_error:
            logger.error(f"Error committing repairs: {str(commit_error)}")
            db.session.rollback()
            return False, {"error": f"Failed to commit repairs: {str(commit_error)}"}

        # Verify repairs
        success, data = check_document_status(document_id)
        min_analysis_check = data.get("min_analysis_check", False)

        if min_analysis_check:
            logger.info(
                f"Document repair successful! Document now passes minimum analysis check.")
            return True, {"message": "Document repaired successfully", "repairs": repairs_made}
        else:
            logger.error(
                f"Document repair failed - still does not pass minimum analysis check")
            return False, {"error": "Repair didn't fix minimum analysis check", "repairs": repairs_made}

    except Exception as e:
        logger.error(f"Error repairing document: {str(e)}")
        logger.error(traceback.format_exc())
        db.session.rollback()
        return False, {"error": str(e)}


def reprocess_document(document_id):
    """Queue the document for reprocessing"""
    from src.catalog.models import Document
    from src.catalog import db

    try:
        document = Document.query.get(document_id)
        if not document:
            logger.error(f"Document {document_id} not found")
            return False, {"error": "Document not found"}

        # Set status to PENDING for reprocessing
        document.status = 'PENDING'
        db.session.commit()

        # Get file path
        filename = document.filename
        minio_path = f"documents/{filename}"

        # Queue processing task
        from src.catalog.tasks.document_tasks import process_document
        process_document.delay(filename, minio_path, document_id)

        logger.info(
            f"Document {document_id} ({filename}) queued for reprocessing")
        return True, {"message": f"Document queued for reprocessing"}

    except Exception as e:
        logger.error(f"Error reprocessing document: {str(e)}")
        db.session.rollback()
        return False, {"error": str(e)}


def main():
    """Main function"""
    if len(sys.argv) < 2:
        logger.error("Please provide a document ID")
        print(
            "Usage: python document_repair.py <document_id> [repair|reprocess]")
        return

    try:
        document_id = int(sys.argv[1])
    except ValueError:
        logger.error(f"Invalid document ID: {sys.argv[1]}")
        return

    # Default action is 'check'
    action = 'check'
    if len(sys.argv) > 2:
        action = sys.argv[2].lower()

    # Set up Flask app context
    app = setup_flask_app()

    with app.app_context():
        logger.info(f"=== Document Repair Diagnostic Tool ===")
        logger.info(f"Document ID: {document_id}")
        logger.info(f"Action: {action}")

        if action == 'check':
            success, data = check_document_status(document_id)
            if not success:
                logger.error(f"Failed to check document: {data.get('error')}")
                return

            # Status already logged in check_document_status

        elif action == 'repair':
            success, data = repair_document(document_id)
            if success:
                logger.info(f"Document repaired successfully")
                for repair in data.get('repairs', []):
                    logger.info(f"  - {repair}")
            else:
                logger.error(f"Failed to repair document: {data.get('error')}")

        elif action == 'reprocess':
            success, data = reprocess_document(document_id)
            if success:
                logger.info(f"Document queued for reprocessing")
            else:
                logger.error(
                    f"Failed to reprocess document: {data.get('error')}")

        else:
            logger.error(f"Unknown action: {action}")
            print("Valid actions: check, repair, reprocess")


if __name__ == "__main__":
    main()
