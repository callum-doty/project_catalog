# app/services/scorecard_service.py
import json
import logging
from catalog.models import DocumentScorecard
from src.catalog import db

logger = logging.getLogger(__name__)


class ScorecardService:
    """Service for managing document quality scorecards"""

    @staticmethod
    def create_scorecard(document_id):
        """Create an initial empty scorecard for a document"""
        try:
            # Check if scorecard already exists
            existing = DocumentScorecard.query.filter_by(
                document_id=document_id).first()
            if existing:
                logger.info(
                    f"Scorecard already exists for document {document_id}")
                return existing

            # Create new scorecard
            scorecard = DocumentScorecard(document_id=document_id)
            db.session.add(scorecard)
            db.session.commit()

            logger.info(f"Created new scorecard for document {document_id}")
            return scorecard
        except Exception as e:
            db.session.rollback()
            logger.error(
                f"Error creating scorecard for document {document_id}: {str(e)}")
            raise

    @staticmethod
    def update_batch1_scores(document_id, metadata_score, text_score, flags=None):
        """Update scores for Batch 1 processing"""
        try:
            scorecard = DocumentScorecard.query.filter_by(
                document_id=document_id).first()
            if not scorecard:
                scorecard = ScorecardService.create_scorecard(document_id)

            # Update scores
            scorecard.metadata_score = metadata_score
            scorecard.text_extraction_score = text_score

            # Store any flags (issues)
            if flags:
                if 'metadata' in flags:
                    scorecard.metadata_flags = json.dumps(flags['metadata'])
                if 'text' in flags:
                    scorecard.text_flags = json.dumps(flags['text'])

            # Check batch success
            batch1_score = metadata_score + text_score
            scorecard.batch1_success = batch1_score >= 20

            # If batch1 fails, flag for review
            if not scorecard.batch1_success:
                scorecard.requires_review = True
                scorecard.review_reason = "Failed to meet Batch 1 minimum requirements"

            # Calculate total
            scorecard.calculate_total_score()

            db.session.commit()
            logger.info(
                f"Updated Batch 1 scores for document {document_id}: metadata={metadata_score}, text={text_score}")

            return scorecard
        except Exception as e:
            db.session.rollback()
            logger.error(
                f"Error updating Batch 1 scores for document {document_id}: {str(e)}")
            raise

    # Similar methods for update_batch2_scores and update_batch3_scores...

    @staticmethod
    def get_review_queue(limit=100, offset=0):
        """Get documents flagged for review"""
        try:
            return DocumentScorecard.query.filter_by(
                requires_review=True,
                reviewed=False
            ).order_by(
                DocumentScorecard.total_score.asc()
            ).offset(offset).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting review queue: {str(e)}")
            return []
