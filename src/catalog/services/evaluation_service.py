# src/catalog/services/evaluation_service.py
import logging
import json
from datetime import datetime, timedelta
from sqlalchemy import func, case
from src.catalog import db
from src.catalog.models import Document, DocumentScorecard
from src.catalog.models import LLMAnalysis, ExtractedText, DesignElement, Entity, Classification

logger = logging.getLogger(__name__)


class EvaluationService:
    """Service for evaluating and scoring document processing quality"""

    def __init__(self):
        # Removed db.__version__ reference that was causing the error
        logger.info("Initializing EvaluationService")

    def get_quality_metrics(self, days=30):
        """Get quality metrics for admin dashboard"""
        try:
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            # Get document counts in the time range
            total_docs = Document.query.filter(
                Document.upload_date >= start_date
            ).count()

            # Get average scores (with safety checks for no documents)
            if total_docs > 0:
                avg_scores = db.session.query(
                    func.avg(DocumentScorecard.metadata_score).label(
                        'metadata'),
                    func.avg(DocumentScorecard.text_extraction_score).label(
                        'text_extraction'),
                    func.avg(DocumentScorecard.classification_score).label(
                        'classification'),
                    func.avg(DocumentScorecard.entity_score).label('entity'),
                    func.avg(DocumentScorecard.design_score).label('design'),
                    func.avg(DocumentScorecard.keyword_score).label('keyword'),
                    func.avg(DocumentScorecard.communication_score).label(
                        'communication'),
                    func.avg(DocumentScorecard.total_score).label('total')
                ).join(
                    Document, DocumentScorecard.document_id == Document.id
                ).filter(
                    Document.upload_date >= start_date
                ).first()

                # Format the scores
                average_scores = {
                    'metadata': round(avg_scores.metadata or 0, 1),
                    'text_extraction': round(avg_scores.text_extraction or 0, 1),
                    'classification': round(avg_scores.classification or 0, 1),
                    'entity': round(avg_scores.entity or 0, 1),
                    'design': round(avg_scores.design or 0, 1),
                    'keyword': round(avg_scores.keyword or 0, 1),
                    'communication': round(avg_scores.communication or 0, 1),
                    'total': round(avg_scores.total or 0, 1)
                }
            else:
                # Default values if no documents
                average_scores = {
                    'metadata': 0,
                    'text_extraction': 0,
                    'classification': 0,
                    'entity': 0,
                    'design': 0,
                    'keyword': 0,
                    'communication': 0,
                    'total': 0
                }

            # Get success rates
            success_rates = {
                'batch1': 0,
                'batch2': 0,
                'batch3': 0
            }

            if total_docs > 0:
                try:
                    # Fixed case syntax - separate when clauses instead of list
                    success_data = db.session.query(
                        func.sum(
                            case(
                                (DocumentScorecard.batch1_success == True, 1),
                                else_=0
                            )
                        ).label('batch1_success'),
                        func.sum(
                            case(
                                (DocumentScorecard.batch2_success == True, 1),
                                else_=0
                            )
                        ).label('batch2_success'),
                        func.sum(
                            case(
                                (DocumentScorecard.batch3_success == True, 1),
                                else_=0
                            )
                        ).label('batch3_success'),
                        func.count().label('total')
                    ).join(
                        Document, DocumentScorecard.document_id == Document.id
                    ).filter(
                        Document.upload_date >= start_date
                    ).first()

                    if success_data and success_data.total > 0:
                        success_rates = {
                            'batch1': round((success_data.batch1_success or 0) / success_data.total * 100, 1),
                            'batch2': round((success_data.batch2_success or 0) / success_data.total * 100, 1),
                            'batch3': round((success_data.batch3_success or 0) / success_data.total * 100, 1)
                        }
                except Exception as e:
                    logger.error(f"Error calculating success rates: {str(e)}")

            # Get documents requiring review
            try:
                review_count = db.session.query(
                    func.count()
                ).join(
                    Document, DocumentScorecard.document_id == Document.id
                ).filter(
                    Document.upload_date >= start_date,
                    DocumentScorecard.requires_review == True,
                    DocumentScorecard.reviewed == False
                ).scalar() or 0
            except Exception as e:
                logger.error(f"Error calculating review count: {str(e)}")
                review_count = 0

            # Get score distribution
            score_distribution = {
                'range_0_20': 0,
                'range_21_40': 0,
                'range_41_60': 0,
                'range_61_80': 0,
                'range_81_100': 0
            }

            if total_docs > 0:
                for score_range in score_distribution.keys():
                    try:
                        low, high = map(int, score_range.replace(
                            'range_', '').split('_'))

                        count = db.session.query(
                            func.count()
                        ).join(
                            Document, DocumentScorecard.document_id == Document.id
                        ).filter(
                            Document.upload_date >= start_date,
                            DocumentScorecard.total_score >= low,
                            DocumentScorecard.total_score <= high
                        ).scalar() or 0

                        score_distribution[score_range] = count
                    except Exception as e:
                        logger.error(
                            f"Error calculating score distribution for {score_range}: {str(e)}")

            # Compile metrics
            metrics = {
                'period_days': days,
                'total_documents': total_docs,
                'average_scores': average_scores,
                'success_rates': success_rates,
                'review_metrics': {
                    'requires_review_count': review_count,
                    'review_percentage': round((review_count / total_docs * 100), 1) if total_docs > 0 else 0
                },
                'score_distribution': score_distribution,
                'component_scores': {
                    'metadata': average_scores['metadata'],
                    'text_extraction': average_scores['text_extraction'],
                    'classification': average_scores['classification'],
                    'entity': average_scores['entity'],
                    'design': average_scores['design'],
                    'keyword': average_scores['keyword'],
                    'communication': average_scores['communication']
                }
            }

            return metrics

        except Exception as e:
            logger.exception(f"Error calculating quality metrics: {str(e)}")
            # Return minimal data structure to avoid frontend errors
            return {
                'period_days': days,
                'total_documents': 0,
                'average_scores': {'total': 0},
                'success_rates': {'batch1': 0, 'batch2': 0, 'batch3': 0},
                'review_metrics': {'requires_review_count': 0, 'review_percentage': 0},
                'score_distribution': {},
                'component_scores': {}
            }

    def evaluate_batch1(self, document_id):
        """Evaluate Batch 1 components - metadata and text extraction"""
        try:
            document = Document.query.get(document_id)
            if not document:
                logger.error(f"Document {document_id} not found")
                return False, "Document not found"

            # Get scorecard or create one
            scorecard = DocumentScorecard.query.filter_by(
                document_id=document_id).first()
            if not scorecard:
                scorecard = DocumentScorecard(document_id=document_id)
                db.session.add(scorecard)

            # Get components
            llm_analysis = LLMAnalysis.query.filter_by(
                document_id=document_id).first()
            extracted_text = ExtractedText.query.filter_by(
                document_id=document_id).first()

            # Evaluate metadata (20 points max)
            metadata_score = 0
            metadata_flags = []

            if llm_analysis:
                # 5 points for summary
                if llm_analysis.summary_description and len(llm_analysis.summary_description) > 20:
                    metadata_score += 5
                else:
                    metadata_flags.append("Missing or incomplete summary")

                # 5 points for campaign type
                if llm_analysis.campaign_type:
                    metadata_score += 5
                else:
                    metadata_flags.append("Missing campaign type")

                # 5 points for document tone
                if llm_analysis.document_tone:
                    metadata_score += 5
                else:
                    metadata_flags.append("Missing document tone")

                # 5 points for visual analysis
                if llm_analysis.visual_analysis and len(llm_analysis.visual_analysis) > 20:
                    metadata_score += 5
                else:
                    metadata_flags.append(
                        "Missing or incomplete visual analysis")
            else:
                metadata_flags.append("No LLM analysis found")

            # Evaluate text extraction (20 points max)
            text_score = 0
            text_flags = []

            if extracted_text:
                # 10 points for main text content
                if extracted_text.text_content and len(extracted_text.text_content) > 50:
                    text_score += 10
                else:
                    text_flags.append("Missing or incomplete text content")

                # 5 points for main message
                if extracted_text.main_message and len(extracted_text.main_message) > 10:
                    text_score += 5
                else:
                    text_flags.append("Missing or incomplete main message")

                # 5 points for call to action
                if extracted_text.call_to_action:
                    text_score += 5
                else:
                    text_flags.append("Missing call to action")
            else:
                text_flags.append("No extracted text found")

            # Update scorecard
            scorecard.metadata_score = metadata_score
            scorecard.text_extraction_score = text_score
            scorecard.metadata_flags = json.dumps(metadata_flags)
            scorecard.text_flags = json.dumps(text_flags)

            # Determine batch success
            batch_score = metadata_score + text_score
            min_required = 20  # Minimum 20/40 points for batch 1
            scorecard.batch1_success = batch_score >= min_required

            # Calculate total score
            scorecard.calculate_total_score()
            scorecard.check_batch_success()

            # Save to database
            db.session.commit()

            return scorecard.batch1_success, f"Batch 1 score: {batch_score}/40"

        except Exception as e:
            logger.exception(f"Error evaluating Batch 1: {str(e)}")
            db.session.rollback()
            return False, f"Error: {str(e)}"

    def evaluate_batch2(self, document_id):
        """Evaluate Batch 2 components - classification, entity, design"""
        try:
            document = Document.query.get(document_id)
            if not document:
                logger.error(f"Document {document_id} not found")
                return False, "Document not found"

            # Get scorecard or create one
            scorecard = DocumentScorecard.query.filter_by(
                document_id=document_id).first()
            if not scorecard:
                scorecard = DocumentScorecard(document_id=document_id)
                db.session.add(scorecard)

            # Get components
            classification = Classification.query.filter_by(
                document_id=document_id).first()
            entity = Entity.query.filter_by(document_id=document_id).first()
            design = DesignElement.query.filter_by(
                document_id=document_id).first()

            # Evaluate classification (10 points max)
            classification_score = 0
            classification_flags = []

            if classification:
                # 5 points for category
                if classification.category:
                    classification_score += 5
                else:
                    classification_flags.append(
                        "Missing classification category")

                # 5 points for confidence score
                if classification.confidence and classification.confidence > 50:
                    classification_score += 5
                else:
                    classification_flags.append(
                        "Low classification confidence")
            else:
                classification_flags.append("No classification data found")

            # Evaluate entity info (10 points max)
            entity_score = 0
            entity_flags = []

            if entity:
                # 5 points for client name
                if entity.client_name:
                    entity_score += 5
                else:
                    entity_flags.append("Missing client name")

                # 5 points for opponent name
                if entity.opponent_name:
                    entity_score += 5
                else:
                    entity_flags.append("Missing opponent name")
            else:
                entity_flags.append("No entity data found")

            # Evaluate design elements (15 points max)
            design_score = 0
            design_flags = []

            if design:
                # 5 points for color scheme
                if design.color_scheme:
                    design_score += 5
                else:
                    design_flags.append("Missing color scheme")

                # 5 points for geographic location
                if design.geographic_location:
                    design_score += 5
                else:
                    design_flags.append("Missing geographic location")

                # 5 points for target audience
                if design.target_audience:
                    design_score += 5
                else:
                    design_flags.append("Missing target audience")
            else:
                design_flags.append("No design element data found")

            # Update scorecard
            scorecard.classification_score = classification_score
            scorecard.entity_score = entity_score
            scorecard.design_score = design_score
            scorecard.classification_flags = json.dumps(classification_flags)
            scorecard.entity_flags = json.dumps(entity_flags)
            scorecard.design_flags = json.dumps(design_flags)

            # Determine batch success
            batch_score = classification_score + entity_score + design_score
            min_required = 18  # Minimum 18/35 points for batch 2
            scorecard.batch2_success = batch_score >= min_required

            # Calculate total score
            scorecard.calculate_total_score()
            scorecard.check_batch_success()

            # Save to database
            db.session.commit()

            return scorecard.batch2_success, f"Batch 2 score: {batch_score}/35"

        except Exception as e:
            logger.exception(f"Error evaluating Batch 2: {str(e)}")
            db.session.rollback()
            return False, f"Error: {str(e)}"

    def evaluate_batch3(self, document_id):
        """Evaluate Batch 3 components - keywords, communication focus"""
        try:
            document = Document.query.get(document_id)
            if not document:
                logger.error(f"Document {document_id} not found")
                return False, "Document not found"

            # Get scorecard or create one
            scorecard = DocumentScorecard.query.filter_by(
                document_id=document_id).first()
            if not scorecard:
                scorecard = DocumentScorecard(document_id=document_id)
                db.session.add(scorecard)

            # Get components
            llm_analysis = LLMAnalysis.query.filter_by(
                document_id=document_id).first()
            communication_focus = None
            try:
                from src.catalog.models import CommunicationFocus
                communication_focus = CommunicationFocus.query.filter_by(
                    document_id=document_id).first()
            except Exception as e:
                logger.warning(f"Could not get communication focus: {str(e)}")

            # Get hierarchical keywords
            keywords = []
            try:
                from src.catalog.models import DocumentKeyword, KeywordTaxonomy
                keywords = db.session.query(DocumentKeyword, KeywordTaxonomy)\
                    .join(KeywordTaxonomy, DocumentKeyword.taxonomy_id == KeywordTaxonomy.id)\
                    .filter(DocumentKeyword.document_id == document_id).all()
            except Exception as e:
                logger.warning(
                    f"Could not get hierarchical keywords: {str(e)}")

            # Evaluate keywords (15 points max)
            keyword_score = 0
            keyword_flags = []

            # Check for LLM keywords
            if llm_analysis and llm_analysis.keywords and len(llm_analysis.keywords) > 0:
                # 5 points for having any keywords
                keyword_score += 5

                # 5 points for having at least 3 keywords
                if len(llm_analysis.keywords) >= 3:
                    keyword_score += 5
                else:
                    keyword_flags.append("Less than 3 keywords")
            else:
                keyword_flags.append("No LLM keywords found")

            # Check for hierarchical keywords
            if keywords and len(keywords) > 0:
                # 5 points for having hierarchical keywords
                keyword_score += 5
            else:
                keyword_flags.append("No hierarchical keywords found")

            # Evaluate communication focus (10 points max)
            communication_score = 0
            communication_flags = []

            if communication_focus:
                # 5 points for primary issue
                if communication_focus.primary_issue:
                    communication_score += 5
                else:
                    communication_flags.append("Missing primary issue")

                # 5 points for messaging strategy
                if communication_focus.messaging_strategy:
                    communication_score += 5
                else:
                    communication_flags.append("Missing messaging strategy")
            else:
                communication_flags.append("No communication focus data found")

            # Update scorecard
            scorecard.keyword_score = keyword_score
            scorecard.communication_score = communication_score
            scorecard.keyword_flags = json.dumps(keyword_flags)
            scorecard.communication_flags = json.dumps(communication_flags)

            # Determine batch success
            batch_score = keyword_score + communication_score
            min_required = 15  # Minimum 15/25 points for batch 3
            scorecard.batch3_success = batch_score >= min_required

            # Calculate total score
            scorecard.calculate_total_score()
            scorecard.check_batch_success()

            # Save to database
            db.session.commit()

            return scorecard.batch3_success, f"Batch 3 score: {batch_score}/25"

        except Exception as e:
            logger.exception(f"Error evaluating Batch 3: {str(e)}")
            db.session.rollback()
            return False, f"Error: {str(e)}"

    def mark_document_reviewed(self, document_id, reviewer_notes="", corrections_made=""):
        """Mark a document as reviewed"""
        try:
            # Get scorecard
            scorecard = DocumentScorecard.query.filter_by(
                document_id=document_id).first()
            if not scorecard:
                logger.error(f"Scorecard for document {document_id} not found")
                return False

            # Update review fields
            scorecard.reviewed = True
            scorecard.review_date = datetime.utcnow()
            scorecard.reviewer_notes = reviewer_notes
            scorecard.corrections_made = corrections_made

            # Save changes
            db.session.commit()
            logger.info(f"Document {document_id} marked as reviewed")

            return True

        except Exception as e:
            logger.exception(f"Error marking document as reviewed: {str(e)}")
            db.session.rollback()
            return False
