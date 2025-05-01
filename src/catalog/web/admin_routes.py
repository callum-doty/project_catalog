from flask import Blueprint, jsonify, request
from src.catalog.services.evaluation_service import EvaluationService
from src.catalog.models import Document, DocumentScorecard
from src.catalog import db
from datetime import datetime, timedelta
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


@admin_bp.route('/quality-metrics', methods=['GET'])
def get_quality_metrics():
    """Get quality metrics for the admin dashboard"""
    try:
        # Get time range from query params (default to last 30 days)
        days = int(request.args.get('days', 30))

        # Initialize evaluation service
        eval_service = EvaluationService()

        # Get quality metrics
        metrics = eval_service.get_quality_metrics(days=days)

        return jsonify({
            'success': True,
            'data': metrics
        })
    except Exception as e:
        logger.error(f"Error getting quality metrics: {str(e)}")
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

        # Build query
        query = db.session.query(Document, DocumentScorecard)\
            .join(DocumentScorecard, Document.id == DocumentScorecard.document_id)\
            .filter(DocumentScorecard.requires_review == True, DocumentScorecard.reviewed == False)

        # Apply sorting
        if sort_by == 'score':
            query = query.order_by(
                DocumentScorecard.total_score.asc() if sort_order == 'asc'
                else DocumentScorecard.total_score.desc()
            )
        else:  # date
            query = query.order_by(
                Document.upload_date.asc() if sort_order == 'asc'
                else Document.upload_date.desc()
            )

        # Apply pagination
        paginated = query.paginate(page=page, per_page=per_page)

        # Format results
        results = []
        for doc, scorecard in paginated.items:
            doc_info = {
                'document_id': doc.id,
                'filename': doc.filename,
                'upload_date': doc.upload_date.isoformat(),
                'status': doc.status,
                'scorecard': {
                    'total_score': scorecard.total_score,
                    'requires_review': scorecard.requires_review,
                    'review_reason': scorecard.review_reason,
                    'batch1_success': scorecard.batch1_success,
                    'batch2_success': scorecard.batch2_success,
                    'batch3_success': scorecard.batch3_success,
                    'review_priority': 'HIGH' if scorecard.total_score < 40
                    else 'MEDIUM' if scorecard.total_score < 60
                    else 'LOW'
                }
            }
            results.append(doc_info)

        return jsonify({
            'success': True,
            'data': {
                'items': results,
                'total': paginated.total,
                'pages': paginated.pages,
                'current_page': paginated.page
            }
        })
    except Exception as e:
        logger.error(f"Error getting review queue: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_bp.route('/component-performance', methods=['GET'])
def get_component_performance():
    """Get performance metrics for each processing component"""
    try:
        # Get time range from query params
        days = int(request.args.get('days', 30))

        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Query for component performance
        performance = db.session.query(
            db.func.avg(DocumentScorecard.metadata_score).label(
                'avg_metadata'),
            db.func.avg(DocumentScorecard.text_extraction_score).label(
                'avg_text'),
            db.func.avg(DocumentScorecard.classification_score).label(
                'avg_classification'),
            db.func.avg(DocumentScorecard.entity_score).label('avg_entity'),
            db.func.avg(DocumentScorecard.design_score).label('avg_design'),
            db.func.avg(DocumentScorecard.keyword_score).label('avg_keyword'),
            db.func.avg(DocumentScorecard.communication_score).label(
                'avg_communication'),
            db.func.count().label('total_documents')
        ).join(Document, DocumentScorecard.document_id == Document.id)\
            .filter(Document.upload_date >= start_date).first()

        # Calculate success rates
        success_rates = db.session.query(
            db.func.sum(db.case([(DocumentScorecard.batch1_success == True, 1)], else_=0)).label(
                'batch1_success'),
            db.func.sum(db.case([(DocumentScorecard.batch2_success == True, 1)], else_=0)).label(
                'batch2_success'),
            db.func.sum(db.case([(DocumentScorecard.batch3_success == True, 1)], else_=0)).label(
                'batch3_success'),
            db.func.count().label('total')
        ).join(Document, DocumentScorecard.document_id == Document.id)\
            .filter(Document.upload_date >= start_date).first()

        # Format results
        result = {
            'period_days': days,
            'component_scores': {
                'metadata': round(performance.avg_metadata or 0, 1),
                'text_extraction': round(performance.avg_text or 0, 1),
                'classification': round(performance.avg_classification or 0, 1),
                'entity': round(performance.avg_entity or 0, 1),
                'design': round(performance.avg_design or 0, 1),
                'keyword': round(performance.avg_keyword or 0, 1),
                'communication': round(performance.avg_communication or 0, 1)
            },
            'success_rates': {
                'batch1': round((success_rates.batch1_success or 0) / (success_rates.total or 1) * 100, 1),
                'batch2': round((success_rates.batch2_success or 0) / (success_rates.total or 1) * 100, 1),
                'batch3': round((success_rates.batch3_success or 0) / (success_rates.total or 1) * 100, 1)
            },
            'total_documents': performance.total_documents or 0
        }

        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        logger.error(f"Error getting component performance: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_bp.route('/review/<int:document_id>', methods=['POST'])
def review_document(document_id: int):
    """Process a document review"""
    try:
        data = request.get_json()
        reviewer_notes = data.get('reviewer_notes')
        corrections_made = data.get('corrections_made')
        action = data.get('action')  # 'approve' or 'reject'

        # Initialize evaluation service
        eval_service = EvaluationService()

        # Mark document as reviewed
        success = eval_service.mark_document_reviewed(
            document_id=document_id,
            reviewer_notes=reviewer_notes,
            corrections_made=corrections_made
        )

        if not success:
            return jsonify({
                'success': False,
                'error': 'Failed to process review'
            }), 400

        return jsonify({
            'success': True,
            'message': f'Document {document_id} review processed successfully'
        })
    except Exception as e:
        logger.error(
            f"Error processing review for document {document_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
