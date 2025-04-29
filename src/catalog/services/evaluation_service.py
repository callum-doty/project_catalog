# src/catalog/services/evaluation_service.py
"""
Evaluation Service for document processing quality assessment.

This service implements the quality evaluation framework for document processing,
providing scoring and assessment functionality at each processing checkpoint.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional, Union

from src.catalog import db
from src.catalog.models import Document, LLMAnalysis, ExtractedText, Classification
from src.catalog.models import DesignElement, Entity, CommunicationFocus, DocumentKeyword
from src.catalog.models.scoring import DocumentScorecard

logger = logging.getLogger(__name__)


class EvaluationService:
    """Service for evaluating document processing quality at various checkpoints."""

    def __init__(self):
        """Initialize the evaluation service with default settings."""
        self.logger = logging.getLogger(__name__)

        # Minimum threshold scores
        self.min_batch1_score = 20  # Out of 40 points
        self.min_batch2_score = 18  # Out of 35 points
        self.min_batch3_score = 15  # Out of 25 points
        self.min_total_score = 55   # Out of 100 points

        # Score distribution weights
        self.metadata_weight = 20   # Points for metadata
        self.text_weight = 20       # Points for text extraction
        self.classification_weight = 10  # Points for classification
        self.entity_weight = 10     # Points for entity extraction
        self.design_weight = 15     # Points for design analysis
        self.keyword_weight = 15    # Points for keywords
        self.communication_weight = 10  # Points for communication analysis

    def create_or_get_scorecard(self, document_id: int) -> DocumentScorecard:
        """Create a new scorecard or get existing one for a document."""
        try:
            # Check if scorecard already exists
            scorecard = DocumentScorecard.query.filter_by(
                document_id=document_id).first()

            if not scorecard:
                # Create new scorecard
                scorecard = DocumentScorecard(
                    document_id=document_id,
                    created_date=datetime.utcnow(),
                    updated_date=datetime.utcnow()
                )
                db.session.add(scorecard)
                db.session.commit()
                self.logger.info(
                    f"Created new scorecard for document {document_id}")

            return scorecard
        except Exception as e:
            self.logger.error(
                f"Error creating/getting scorecard for document {document_id}: {str(e)}")
            db.session.rollback()
            raise

    def evaluate_batch1(self, document_id: int) -> Tuple[bool, Dict[str, Any]]:
        """
        Evaluate Batch 1 processing results (metadata and text extraction).

        Args:
            document_id: The document ID to evaluate

        Returns:
            Tuple of (success_flag, details_dict)
        """
        try:
            # Get document and related data
            document = Document.query.get(document_id)
            if not document:
                self.logger.error(f"Document {document_id} not found")
                return False, {"error": "Document not found"}

            # Get or create scorecard
            scorecard = self.create_or_get_scorecard(document_id)

            # Get relevant components
            llm_analysis = LLMAnalysis.query.filter_by(
                document_id=document_id).first()
            extracted_text = ExtractedText.query.filter_by(
                document_id=document_id).first()

            # Start with zero scores
            metadata_score = 0
            text_score = 0
            metadata_flags = []
            text_flags = []

            # Evaluate metadata (total: 20 points)
            if llm_analysis:
                # Document summary (5 points)
                if llm_analysis.summary_description and len(llm_analysis.summary_description.strip()) > 10:
                    metadata_score += 5
                else:
                    metadata_flags.append(
                        "Missing or inadequate document summary")

                # Campaign type (5 points)
                if llm_analysis.campaign_type and len(llm_analysis.campaign_type.strip()) > 0:
                    metadata_score += 5
                else:
                    metadata_flags.append("Missing campaign type")

                # Election year (5 points)
                if llm_analysis.election_year and len(llm_analysis.election_year.strip()) > 0:
                    metadata_score += 5
                else:
                    metadata_flags.append("Missing election year")

                # Document tone (5 points)
                if llm_analysis.document_tone and len(llm_analysis.document_tone.strip()) > 0:
                    metadata_score += 5
                else:
                    metadata_flags.append("Missing document tone")
            else:
                metadata_flags.append("Missing LLM analysis entirely")

            # Evaluate text extraction (total: 20 points)
            if extracted_text:
                # Main message (5 points)
                if extracted_text.main_message and len(extracted_text.main_message.strip()) > 5:
                    text_score += 5
                else:
                    text_flags.append("Missing or inadequate main message")

                # Supporting text (5 points)
                if extracted_text.supporting_text and len(extracted_text.supporting_text.strip()) > 10:
                    text_score += 5
                else:
                    text_flags.append("Missing or inadequate supporting text")

                # Call-to-action (3 points)
                if extracted_text.call_to_action and len(extracted_text.call_to_action.strip()) > 0:
                    text_score += 3

                # Candidate/opponent names (7 points)
                if extracted_text.candidate_name and len(extracted_text.candidate_name.strip()) > 1:
                    text_score += 4
                else:
                    text_flags.append("Missing candidate name")

                if extracted_text.opponent_name and len(extracted_text.opponent_name.strip()) > 1:
                    text_score += 3
            else:
                text_flags.append("Missing extracted text entirely")

            # Update scorecard with Batch 1 results
            scorecard.metadata_score = metadata_score
            scorecard.text_extraction_score = text_score
            scorecard.metadata_flags = json.dumps(
                metadata_flags) if metadata_flags else None
            scorecard.text_flags = json.dumps(
                text_flags) if text_flags else None

            # Calculate batch success
            batch1_total = metadata_score + text_score
            scorecard.batch1_success = batch1_total >= self.min_batch1_score

            # Calculate interim total score
            scorecard.total_score = batch1_total

            # Update scorecard
            scorecard.updated_date = datetime.utcnow()
            db.session.commit()

            result_details = {
                "metadata_score": metadata_score,
                "text_score": text_score,
                "total_batch1_score": batch1_total,
                "metadata_flags": metadata_flags,
                "text_flags": text_flags,
                "batch1_success": scorecard.batch1_success
            }

            self.logger.info(
                f"Batch 1 evaluation for document {document_id}: {result_details}")
            return scorecard.batch1_success, result_details

        except Exception as e:
            self.logger.error(
                f"Error evaluating Batch 1 for document {document_id}: {str(e)}")
            db.session.rollback()
            return False, {"error": str(e)}

    def evaluate_batch2(self, document_id: int) -> Tuple[bool, Dict[str, Any]]:
        """
        Evaluate Batch 2 processing results (classification, entity, and design).

        Args:
            document_id: The document ID to evaluate

        Returns:
            Tuple of (success_flag, details_dict)
        """
        try:
            # Get document and related data
            document = Document.query.get(document_id)
            if not document:
                self.logger.error(f"Document {document_id} not found")
                return False, {"error": "Document not found"}

            # Get or create scorecard
            scorecard = self.create_or_get_scorecard(document_id)

            # Get relevant components
            classification = Classification.query.filter_by(
                document_id=document_id).first()
            entity = Entity.query.filter_by(document_id=document_id).first()
            design = DesignElement.query.filter_by(
                document_id=document_id).first()

            # Start with zero scores
            classification_score = 0
            entity_score = 0
            design_score = 0
            classification_flags = []
            entity_flags = []
            design_flags = []

            # Evaluate classification (total: 10 points)
            if classification:
                # Category accuracy (10 points)
                if classification.category and len(classification.category.strip()) > 0:
                    classification_score = 10
                else:
                    classification_flags.append("Missing document category")
            else:
                classification_flags.append("Missing classification entirely")

            # Evaluate entity extraction (total: 10 points)
            if entity:
                # Client/candidate identification (5 points)
                if entity.client_name and len(entity.client_name.strip()) > 1:
                    entity_score += 5
                else:
                    entity_flags.append("Missing client/candidate name")

                # Opponent identification and auxiliary info (5 points)
                aux_score = 0
                if entity.opponent_name and len(entity.opponent_name.strip()) > 1:
                    aux_score += 2

                if entity.creation_date and len(entity.creation_date.strip()) > 0:
                    aux_score += 1

                if entity.survey_question and len(entity.survey_question.strip()) > 0:
                    aux_score += 1

                if entity.file_identifier and len(entity.file_identifier.strip()) > 0:
                    aux_score += 1

                entity_score += aux_score

                if aux_score < 3:
                    entity_flags.append(
                        "Incomplete auxiliary entity information")
            else:
                entity_flags.append("Missing entity information entirely")

            # Evaluate design element analysis (total: 15 points)
            if design:
                # Format identification (5 points)
                format_score = 0
                if design.mail_piece_type and len(design.mail_piece_type.strip()) > 0:
                    format_score += 3

                if design.theme and len(design.theme.strip()) > 0:
                    format_score += 2

                if format_score < 3:
                    design_flags.append("Incomplete format identification")

                design_score += format_score

                # Visual element inventory (5 points)
                try:
                    visual_elements = json.loads(
                        design.visual_elements) if design.visual_elements else []
                    if visual_elements and len(visual_elements) > 0:
                        # Score based on number of elements (up to 5 points)
                        visual_score = min(len(visual_elements), 5)
                        design_score += visual_score
                    else:
                        design_flags.append("Missing visual element inventory")
                except:
                    design_flags.append("Invalid visual element data format")

                # Geographic/audience targeting (5 points)
                target_score = 0
                if design.geographic_location and len(design.geographic_location.strip()) > 0:
                    target_score += 3

                if design.target_audience and len(design.target_audience.strip()) > 0:
                    target_score += 2

                if target_score < 3:
                    design_flags.append("Incomplete targeting information")

                design_score += target_score
            else:
                design_flags.append("Missing design element analysis entirely")

            # Update scorecard with Batch 2 results
            scorecard.classification_score = classification_score
            scorecard.entity_score = entity_score
            scorecard.design_score = design_score
            scorecard.classification_flags = json.dumps(
                classification_flags) if classification_flags else None
            scorecard.entity_flags = json.dumps(
                entity_flags) if entity_flags else None
            scorecard.design_flags = json.dumps(
                design_flags) if design_flags else None

            # Calculate batch success
            batch2_total = classification_score + entity_score + design_score
            scorecard.batch2_success = batch2_total >= self.min_batch2_score

            # Update total score (accumulate with batch 1)
            if scorecard.total_score is not None:
                scorecard.total_score = (
                    scorecard.metadata_score or 0) + (scorecard.text_extraction_score or 0) + batch2_total
            else:
                scorecard.total_score = batch2_total

            # Update scorecard
            scorecard.updated_date = datetime.utcnow()
            db.session.commit()

            result_details = {
                "classification_score": classification_score,
                "entity_score": entity_score,
                "design_score": design_score,
                "total_batch2_score": batch2_total,
                "classification_flags": classification_flags,
                "entity_flags": entity_flags,
                "design_flags": design_flags,
                "batch2_success": scorecard.batch2_success
            }

            self.logger.info(
                f"Batch 2 evaluation for document {document_id}: {result_details}")
            return scorecard.batch2_success, result_details

        except Exception as e:
            self.logger.error(
                f"Error evaluating Batch 2 for document {document_id}: {str(e)}")
            db.session.rollback()
            return False, {"error": str(e)}

    def evaluate_batch3(self, document_id: int) -> Tuple[bool, Dict[str, Any]]:
        """
        Evaluate Batch 3 processing results (keywords and communication).

        Args:
            document_id: The document ID to evaluate

        Returns:
            Tuple of (success_flag, details_dict)
        """
        try:
            # Get document and related data
            document = Document.query.get(document_id)
            if not document:
                self.logger.error(f"Document {document_id} not found")
                return False, {"error": "Document not found"}

            # Get or create scorecard
            scorecard = self.create_or_get_scorecard(document_id)

            # Get relevant components
            communication = CommunicationFocus.query.filter_by(
                document_id=document_id).first()
            doc_keywords = DocumentKeyword.query.filter_by(
                document_id=document_id).all()

            # Start with zero scores
            keyword_score = 0
            communication_score = 0
            keyword_flags = []
            communication_flags = []

            # Evaluate keywords (total: 15 points)
            if doc_keywords and len(doc_keywords) > 0:
                # Score based on number of keywords (up to 10 points)
                count_score = min(len(doc_keywords), 10)
                keyword_score += count_score

                # Check taxonomy categorization (5 points)
                taxonomy_categories = set()
                for kw in doc_keywords:
                    if kw.taxonomy_term:
                        taxonomy_categories.add(
                            kw.taxonomy_term.primary_category)

                # Add points based on category diversity (up to 5 points)
                category_score = min(len(taxonomy_categories), 5)
                keyword_score += category_score

                if len(doc_keywords) < 5:
                    keyword_flags.append(
                        "Insufficient number of keywords extracted")

                if len(taxonomy_categories) < 2:
                    keyword_flags.append("Limited taxonomy category coverage")
            else:
                keyword_flags.append("Missing keywords entirely")

            # Evaluate communication focus (total: 10 points)
            if communication:
                # Primary issue identification (5 points)
                if communication.primary_issue and len(communication.primary_issue.strip()) > 0:
                    communication_score += 5
                else:
                    communication_flags.append("Missing primary issue")

                # Secondary issues and messaging (5 points)
                aux_score = 0

                # Check secondary issues
                try:
                    secondary_issues = json.loads(
                        communication.secondary_issues) if communication.secondary_issues else []
                    if secondary_issues and len(secondary_issues) > 0:
                        aux_score += 3
                except:
                    communication_flags.append(
                        "Invalid secondary issues format")

                # Check messaging strategy
                if communication.messaging_strategy and len(communication.messaging_strategy.strip()) > 0:
                    aux_score += 2

                communication_score += aux_score

                if aux_score < 3:
                    communication_flags.append(
                        "Incomplete communication analysis")
            else:
                communication_flags.append(
                    "Missing communication focus entirely")

            # Update scorecard with Batch 3 results
            scorecard.keyword_score = keyword_score
            scorecard.communication_score = communication_score
            scorecard.keyword_flags = json.dumps(
                keyword_flags) if keyword_flags else None
            scorecard.communication_flags = json.dumps(
                communication_flags) if communication_flags else None

            # Calculate batch success
            batch3_total = keyword_score + communication_score
            scorecard.batch3_success = batch3_total >= self.min_batch3_score

            # Update total score (accumulate with previous batches)
            prev_total = (scorecard.metadata_score or 0) + (scorecard.text_extraction_score or 0) + \
                (scorecard.classification_score or 0) + (scorecard.entity_score or 0) + \
                (scorecard.design_score or 0)

            scorecard.total_score = prev_total + batch3_total

            # Check if document needs review based on total score
            if scorecard.total_score < self.min_total_score:
                scorecard.requires_review = True
                scorecard.review_reason = f"Total score ({scorecard.total_score}) below minimum threshold ({self.min_total_score})"

            # Final evaluation: check if document meets minimum requirements
            overall_success = scorecard.batch1_success and (
                scorecard.batch2_success or scorecard.batch3_success)
            if not overall_success and not scorecard.requires_review:
                scorecard.requires_review = True
                scorecard.review_reason = "Failed to meet minimum batch success criteria"

            # Update scorecard
            scorecard.updated_date = datetime.utcnow()
            db.session.commit()

            result_details = {
                "keyword_score": keyword_score,
                "communication_score": communication_score,
                "total_batch3_score": batch3_total,
                "keyword_flags": keyword_flags,
                "communication_flags": communication_flags,
                "batch3_success": scorecard.batch3_success,
                "total_score": scorecard.total_score,
                "requires_review": scorecard.requires_review,
                "review_reason": scorecard.review_reason
            }

            self.logger.info(
                f"Batch 3 evaluation for document {document_id}: {result_details}")
            return scorecard.batch3_success, result_details

        except Exception as e:
            self.logger.error(
                f"Error evaluating Batch 3 for document {document_id}: {str(e)}")
            db.session.rollback()
            return False, {"error": str(e)}

    def get_document_score(self, document_id: int) -> Optional[Dict[str, Any]]:
        """Get the full scorecard for a document."""
        try:
            scorecard = DocumentScorecard.query.filter_by(
                document_id=document_id).first()
            if not scorecard:
                return None

            # Convert to dictionary
            result = scorecard.to_dict()

            # Parse any JSON fields
            if result.get('metadata_flags'):
                try:
                    result['metadata_flags'] = json.loads(
                        result['metadata_flags'])
                except:
                    pass

            if result.get('text_flags'):
                try:
                    result['text_flags'] = json.loads(result['text_flags'])
                except:
                    pass

            if result.get('classification_flags'):
                try:
                    result['classification_flags'] = json.loads(
                        result['classification_flags'])
                except:
                    pass

            if result.get('entity_flags'):
                try:
                    result['entity_flags'] = json.loads(result['entity_flags'])
                except:
                    pass

            if result.get('design_flags'):
                try:
                    result['design_flags'] = json.loads(result['design_flags'])
                except:
                    pass

            if result.get('keyword_flags'):
                try:
                    result['keyword_flags'] = json.loads(
                        result['keyword_flags'])
                except:
                    pass

            if result.get('communication_flags'):
                try:
                    result['communication_flags'] = json.loads(
                        result['communication_flags'])
                except:
                    pass

            return result
        except Exception as e:
            self.logger.error(
                f"Error getting document score for {document_id}: {str(e)}")
            return None

    def get_documents_for_review(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get documents flagged for review, with their scorecards."""
        try:
            # Query documents with scorecards that require review
            query = db.session.query(Document, DocumentScorecard)\
                .join(DocumentScorecard, Document.id == DocumentScorecard.document_id)\
                .filter(DocumentScorecard.requires_review == True, DocumentScorecard.reviewed == False)\
                .order_by(DocumentScorecard.total_score.asc())\
                .offset(offset).limit(limit)

            results = []
            for doc, scorecard in query.all():
                # Basic document info
                doc_info = {
                    "document_id": doc.id,
                    "filename": doc.filename,
                    "upload_date": doc.upload_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "status": doc.status,
                }

                # Add scorecard info
                doc_info.update({
                    "total_score": scorecard.total_score,
                    "requires_review": scorecard.requires_review,
                    "review_reason": scorecard.review_reason,
                    "batch1_success": scorecard.batch1_success,
                    "batch2_success": scorecard.batch2_success,
                    "batch3_success": scorecard.batch3_success,
                    "review_priority": "HIGH" if scorecard.total_score < 40 else "MEDIUM" if scorecard.total_score < 60 else "LOW"
                })

                results.append(doc_info)

            return results

        except Exception as e:
            self.logger.error(f"Error getting documents for review: {str(e)}")
            return []

    def mark_document_reviewed(self, document_id: int, reviewer_notes: str = None,
                               corrections_made: Dict[str, Any] = None) -> bool:
        """Mark a document as reviewed."""
        try:
            scorecard = DocumentScorecard.query.filter_by(
                document_id=document_id).first()
            if not scorecard:
                return False

            scorecard.reviewed = True
            scorecard.review_date = datetime.utcnow()

            if reviewer_notes:
                scorecard.reviewer_notes = reviewer_notes

            if corrections_made:
                scorecard.corrections_made = json.dumps(corrections_made)

            db.session.commit()
            return True

        except Exception as e:
            self.logger.error(
                f"Error marking document {document_id} as reviewed: {str(e)}")
            db.session.rollback()
            return False

    def get_quality_metrics(self, days: int = 30) -> Dict[str, Any]:
        """Get overall quality metrics for recent documents."""
        try:
            from datetime import datetime, timedelta
            from sqlalchemy import func, case

            # Calculate the date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            # Get basic counts
            total_documents = db.session.query(Document)\
                .filter(Document.upload_date >= start_date).count()

            total_scored = db.session.query(DocumentScorecard)\
                .join(Document, DocumentScorecard.document_id == Document.id)\
                .filter(Document.upload_date >= start_date).count()

            # Calculate average scores
            avg_scores = db.session.query(
                func.avg(DocumentScorecard.total_score).label('avg_total'),
                func.avg(DocumentScorecard.metadata_score).label(
                    'avg_metadata'),
                func.avg(DocumentScorecard.text_extraction_score).label(
                    'avg_text'),
                func.avg(DocumentScorecard.classification_score).label(
                    'avg_classification'),
                func.avg(DocumentScorecard.entity_score).label('avg_entity'),
                func.avg(DocumentScorecard.design_score).label('avg_design'),
                func.avg(DocumentScorecard.keyword_score).label('avg_keyword'),
                func.avg(DocumentScorecard.communication_score).label(
                    'avg_communication')
            ).join(Document, DocumentScorecard.document_id == Document.id)\
                .filter(Document.upload_date >= start_date).first()

            # Calculate success rates
            batch_success = db.session.query(
                func.sum(case([(DocumentScorecard.batch1_success == True, 1)], else_=0)).label(
                    'batch1_success'),
                func.sum(case([(DocumentScorecard.batch2_success == True, 1)], else_=0)).label(
                    'batch2_success'),
                func.sum(case([(DocumentScorecard.batch3_success == True, 1)], else_=0)).label(
                    'batch3_success'),
                func.count().label('total')
            ).join(Document, DocumentScorecard.document_id == Document.id)\
                .filter(Document.upload_date >= start_date).first()

            # Calculate review stats
            review_stats = db.session.query(
                func.sum(case([(DocumentScorecard.requires_review == True, 1)], else_=0)).label(
                    'requires_review'),
                func.sum(case([(DocumentScorecard.reviewed == True, 1)], else_=0)).label(
                    'completed_review'),
                func.count().label('total')
            ).join(Document, DocumentScorecard.document_id == Document.id)\
                .filter(Document.upload_date >= start_date).first()

            # Prepare result
            metrics = {
                "period_days": days,
                "total_documents": total_documents,
                "total_scored": total_scored,
                "average_scores": {
                    "total": round(avg_scores.avg_total or 0, 1),
                    "metadata": round(avg_scores.avg_metadata or 0, 1),
                    "text_extraction": round(avg_scores.avg_text or 0, 1),
                    "classification": round(avg_scores.avg_classification or 0, 1),
                    "entity": round(avg_scores.avg_entity or 0, 1),
                    "design": round(avg_scores.avg_design or 0, 1),
                    "keyword": round(avg_scores.avg_keyword or 0, 1),
                    "communication": round(avg_scores.avg_communication or 0, 1)
                },
                "success_rates": {
                    "batch1": round((batch_success.batch1_success or 0) / (batch_success.total or 1) * 100, 1),
                    "batch2": round((batch_success.batch2_success or 0) / (batch_success.total or 1) * 100, 1),
                    "batch3": round((batch_success.batch3_success or 0) / (batch_success.total or 1) * 100, 1)
                },
                "review_metrics": {
                    "requires_review_count": review_stats.requires_review or 0,
                    "requires_review_percent": round((review_stats.requires_review or 0) / (review_stats.total or 1) * 100, 1),
                    "completed_review_count": review_stats.completed_review or 0,
                    "review_completion_rate": round((review_stats.completed_review or 0) / (review_stats.requires_review or 1) * 100, 1) if review_stats.requires_review else 0
                }
            }

            return metrics

        except Exception as e:
            self.logger.error(f"Error getting quality metrics: {str(e)}")
            return {
                "error": str(e),
                "period_days": days,
                "total_documents": 0
            }
