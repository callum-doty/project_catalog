from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, timedelta
import logging

# Import models
from src.catalog.models import Document, DocumentScorecard
from src.catalog import db

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


@admin_bp.route('/quality-metrics', methods=['GET'])
def get_quality_metrics():
    """Get quality metrics for the admin dashboard"""
    try:
        # Get time range from query params (default to last 30 days)
        days = int(request.args.get('days', 30))
        current_app.logger.info(f"Getting metrics for last {days} days")

        # Import only when needed to avoid circular imports
        from src.catalog.services.evaluation_service import EvaluationService
        eval_service = EvaluationService()

        # Get quality metrics
        metrics = eval_service.get_quality_metrics(days=days)
        current_app.logger.info(f"Retrieved metrics successfully")

        return jsonify({
            'success': True,
            'data': metrics
        })
    except Exception as e:
        current_app.logger.error(
            f"Error getting quality metrics: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_bp.route('/review-queue', methods=['GET'])
def get_review_queue():
    """Get documents flagged for review"""
    try:
        # Get pagination params
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        sort_by = request.args.get('sort_by', 'score')  # score or date
        sort_order = request.args.get('sort_order', 'asc')

        # Build query to get documents requiring review - using select_from to fix ambiguity
        query = db.session.query(Document).select_from(DocumentScorecard).join(
            Document, DocumentScorecard.document_id == Document.id
        ).filter(
            DocumentScorecard.requires_review == True,
            DocumentScorecard.reviewed == False
        )

        # Apply sorting
        if sort_by == 'score':
            if sort_order == 'asc':
                query = query.order_by(DocumentScorecard.total_score.asc())
            else:
                query = query.order_by(DocumentScorecard.total_score.desc())
        else:  # date
            if sort_order == 'asc':
                query = query.order_by(Document.upload_date.asc())
            else:
                query = query.order_by(Document.upload_date.desc())

        # Count total items for pagination
        total_items = query.count()
        total_pages = (total_items + per_page -
                       1) // per_page if per_page > 0 else 0

        # Apply pagination - fetch documents first
        documents = query.offset((page - 1) * per_page).limit(per_page).all()

        # Format results
        formatted_results = []
        for doc in documents:
            # Get scorecard
            scorecard = DocumentScorecard.query.filter_by(
                document_id=doc.id).first()

            # Set review priority based on score
            if scorecard and scorecard.total_score is not None:
                if scorecard.total_score < 40:
                    review_priority = "HIGH"
                elif scorecard.total_score < 60:
                    review_priority = "MEDIUM"
                else:
                    review_priority = "LOW"
            else:
                review_priority = "HIGH"  # Default to high if no score

            # Format document data
            doc_info = {
                'document_id': doc.id,
                'filename': doc.filename,
                'upload_date': doc.upload_date.isoformat(),
                'status': doc.status,
                'scorecard': {
                    'total_score': scorecard.total_score if scorecard else 0,
                    'requires_review': True,
                    'review_reason': scorecard.review_reason if scorecard else "Unknown",
                    'batch1_success': scorecard.batch1_success if scorecard else False,
                    'batch2_success': scorecard.batch2_success if scorecard else False,
                    'batch3_success': scorecard.batch3_success if scorecard else False,
                    'review_priority': review_priority
                }
            }
            formatted_results.append(doc_info)

        # Build pagination info
        pagination = {
            'page': page,
            'per_page': per_page,
            'total': total_items,
            'pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'prev_page': page - 1 if page > 1 else None,
            'next_page': page + 1 if page < total_pages else None
        }

        return jsonify({
            'success': True,
            'data': {
                'items': formatted_results,
                'pagination': pagination
            }
        })
    except Exception as e:
        logger.error(f"Error getting review queue: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_bp.route('/review/<int:document_id>', methods=['POST'])
def review_document(document_id):
    """Process a document review"""
    try:
        data = request.get_json()
        reviewer_notes = data.get('reviewer_notes', '')
        corrections_made = data.get('corrections_made', '')
        action = data.get('action', 'approve')  # 'approve' or 'reject'

        # Get the document
        scorecard = DocumentScorecard.query.filter_by(
            document_id=document_id).first()
        if not scorecard:
            return jsonify({
                'success': False,
                'error': f'No scorecard found for document {document_id}'
            }), 404

        # Update review status
        scorecard.reviewed = True
        scorecard.review_date = datetime.utcnow()
        scorecard.reviewer_notes = reviewer_notes
        scorecard.corrections_made = corrections_made

        # Save changes
        db.session.commit()
        logger.info(f"Document {document_id} reviewed successfully")

        return jsonify({
            'success': True,
            'message': f'Document {document_id} review processed successfully'
        })
    except Exception as e:
        logger.error(
            f"Error processing review for document {document_id}: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_bp.route('/generate-scorecards', methods=['POST'])
def generate_missing_scorecards():
    """Generate evaluation scorecards for all documents that don't have them"""
    try:
        # Import evaluation service
        from src.catalog.services.evaluation_service import EvaluationService

        # Find documents without scorecards - Using EXISTS subquery to avoid ambiguity
        documents_query = db.session.query(Document).filter(
            Document.status == 'COMPLETED',
            ~Document.id.in_(db.session.query(DocumentScorecard.document_id))
        )

        # Count total documents
        total_count = documents_query.count()

        # Limit to 100 documents per request to avoid timeouts
        documents = documents_query.limit(100).all()

        # Create evaluation service
        eval_service = EvaluationService()

        # Initialize counters
        created_count = 0
        error_count = 0

        # Process each document
        for doc in documents:
            try:
                # Evaluate batch 1
                batch1_success, _ = eval_service.evaluate_batch1(doc.id)

                # Evaluate batch 2
                batch2_success, _ = eval_service.evaluate_batch2(doc.id)

                # Evaluate batch 3
                batch3_success, _ = eval_service.evaluate_batch3(doc.id)

                created_count += 1
                current_app.logger.info(
                    f"Created scorecard for document {doc.id}")
            except Exception as e:
                current_app.logger.error(
                    f"Error creating scorecard for document {doc.id}: {str(e)}")
                error_count += 1

        # Return summary
        return jsonify({
            'success': True,
            'message': f"Created {created_count} scorecards with {error_count} errors. {total_count - created_count} documents remaining."
        })
    except Exception as e:
        current_app.logger.error(
            f"Error generating scorecards: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
