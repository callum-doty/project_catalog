# app/routes/main_routes.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from app.services.storage_service import MinIOStorage
from app.extensions import db
from app.models.models import Document, LLMAnalysis, LLMKeyword, Classification, DesignElement, ExtractedText, DropboxSync   
from sqlalchemy import or_, func, desc, case, extract
from app.services.preview_service import PreviewService
from app.services.dropbox_service import DropboxService
from flask_wtf.csrf import generate_csrf
from app import csrf
import time
from datetime import datetime, timedelta
from sqlalchemy.sql.expression import text
import statistics
from statistics import mean
from tasks.document_tasks import process_document


main_routes = Blueprint('main_routes', __name__)
storage = MinIOStorage()
preview_service = PreviewService()
search_times = []
MAX_SEARCH_TIMES = 100

def get_celery_task(task_name):
    """Lazy import of celery tasks to avoid circular imports"""
    if task_name == 'process_document':
        return process_document
    elif task_name == 'sync_dropbox':
        from tasks.dropbox_tasks import sync_dropbox
        return sync_dropbox

def record_search_time(response_time):
    """Record a search response time and maintain the list size"""
    global search_times
    search_times.append(response_time)
    # Keep only the most recent times
    if len(search_times) > MAX_SEARCH_TIMES:
        search_times = search_times[-MAX_SEARCH_TIMES:]

@main_routes.route('/')
def index():
    try:
        documents = Document.query.order_by(Document.upload_date.desc()).limit(10).all()
        formatted_docs = []
        
        for doc in documents:
            # Get preview if possible
            preview = None
            try:
                preview = preview_service.get_preview(doc.filename)
            except Exception as e:
                current_app.logger.error(f"Preview generation failed for {doc.filename}: {str(e)}")
            
            # Format document data
            formatted_doc = {
                'id': doc.id,
                'filename': doc.filename,
                'upload_date': doc.upload_date.strftime('%Y-%m-%d %H:%M:%S'),
                'status': doc.status,
                'preview': preview,
                'summary': doc.llm_analysis.summary_description if doc.llm_analysis else '',
                'keywords': []
            }
            
            # Add keywords if they exist
            if doc.llm_analysis and doc.llm_analysis.keywords:
                formatted_doc['keywords'] = [
                    {
                        'text': kw.keyword,
                        'category': kw.category
                    } for kw in doc.llm_analysis.keywords
                ]
            
            formatted_docs.append(formatted_doc)
            
        return render_template('pages/index.html', documents=formatted_docs)
    except Exception as e:
        current_app.logger.error(f"Error fetching documents: {str(e)}")
        return render_template('pages/index.html', documents=[])


@main_routes.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('main_routes.index'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('main_routes.index'))

    try:
        filename = secure_filename(file.filename)
        temp_path = os.path.join('/tmp', filename)
        file.save(temp_path)
        
        # Create document record FIRST
        document = Document(
            filename=filename,
            upload_date=datetime.utcnow(),
            file_size=os.path.getsize(temp_path),
            status='PENDING',
            page_count=1
        )
        db.session.add(document)
        db.session.commit()
        
        # Now we have a document.id to use
        minio_path = storage.upload_file(temp_path, filename)
        current_app.logger.info(f"Successfully uploaded {filename} to MinIO at {minio_path}")

        # Use the full process_document task instead of test_document_processing
        try:
            current_app.logger.info(f"Queuing document {document.id} for processing")
            from tasks.document_tasks import process_document
            task = process_document.delay(filename, minio_path, document.id)
            current_app.logger.info(f"Task queued with ID: {task.id}")
        except Exception as e:
            current_app.logger.error(f"Failed to queue document for processing: {str(e)}")
            # Even if processing queue fails, we'll still return success for file upload
        
        os.remove(temp_path)
        flash('File uploaded successfully', 'success')
        return redirect(url_for('main_routes.index'))

    except Exception as e:
        current_app.logger.error(f"Upload error: {str(e)}")
        flash(f'Error uploading file: {str(e)}', 'error')
        return redirect(url_for('main_routes.index'))

@main_routes.route('/search')
def search_documents():
    query = request.args.get('q', '')
    start_time = time.time()  # Start timing
    
    try:
        base_query = Document.query

        if query:
            documents = base_query.join(Document.llm_analysis)\
                .outerjoin(LLMKeyword, LLMAnalysis.id == LLMKeyword.llm_analysis_id)\
                .filter(
                    or_(
                        Document.filename.ilike(f'%{query}%'),
                        LLMAnalysis.summary_description.ilike(f'%{query}%'),
                        LLMKeyword.keyword.ilike(f'%{query}%')
                    )
                ).distinct().all()
        else:
            documents = base_query.order_by(Document.upload_date.desc()).all()

        # Format results
        results = []
        for doc in documents:
            # Get preview if possible
            preview = None
            try:
                preview = preview_service.get_preview(doc.filename)
            except Exception as e:
                current_app.logger.error(f"Preview generation failed for {doc.filename}: {str(e)}")
            
            result = {
                'id': doc.id,
                'filename': doc.filename,
                'upload_date': doc.upload_date.strftime('%Y-%m-%d %H:%M:%S'),
                'preview': preview,
                'summary': doc.llm_analysis.summary_description if doc.llm_analysis else '',
                'keywords': []
            }
            
            if doc.llm_analysis and doc.llm_analysis.keywords:
                result['keywords'] = [
                    {
                        'text': kw.keyword,
                        'category': kw.category
                    } for kw in doc.llm_analysis.keywords
                ]
            
            results.append(result)
            
        # Record search time
        response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        record_search_time(response_time)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(results)
        
        return render_template('pages/search.html', documents=results, query=query)
        
    except Exception as e:
        # Still record the time even for errors
        response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        record_search_time(response_time)
        
        current_app.logger.error(f"Search error: {str(e)}")
        return render_template('pages/search.html', documents=[], query=query)

@main_routes.route('/api/sync-dropbox', methods=['POST'])
def trigger_dropbox_sync():  # Renamed function to avoid conflict
    """Manually trigger a Dropbox sync"""
    try:
        current_app.logger.info("Manually triggering Dropbox sync")
        sync_dropbox = get_celery_task('sync_dropbox')
        result = sync_dropbox.delay()
        current_app.logger.info(f"Sync task triggered with ID: {result.id}")
        return jsonify({
            'status': 'success',
            'message': 'Sync task triggered',
            'task_id': result.id
        })
    except Exception as e:
        current_app.logger.error(f"Error triggering sync: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@main_routes.after_request
def add_csrf_token(response):
    """Add CSRF token to response for AJAX requests"""
    if 'text/html' in response.headers['Content-Type']:
        response.set_cookie('csrf_token', generate_csrf())
    return response

@main_routes.route('/api/sync-status')
@csrf.exempt
def get_sync_status():
    """Get Dropbox sync status"""
    try:
        dropbox_service = DropboxService()
        status = dropbox_service.get_sync_status()
        return jsonify(status)
    except Exception as e:
        current_app.logger.error(f"Error getting sync status: {str(e)}")
        return jsonify({
            'error': 'Failed to get sync status',
            'last_sync_time': None,
            'last_24h_files': 0,
            'last_status': 'ERROR',
            'dropbox_connected': False
        })



@main_routes.route('/api/reprocess-failed', methods=['POST'])
def reprocess_failed():
    """API endpoint to reprocess failed documents"""
    try:
        from tasks.recovery_tasks import reprocess_failed_documents
        
        # Get parameters with defaults
        delay_seconds = int(request.json.get('delay_seconds', 10))
        batch_size = int(request.json.get('batch_size', 5))
        
        # Validate parameters
        if delay_seconds < 0:
            delay_seconds = 0
        if batch_size < 1:
            batch_size = 1
        elif batch_size > 20:
            batch_size = 20
            
        # Start the task
        task = reprocess_failed_documents.delay(delay_seconds, batch_size)
        
        return jsonify({
            'status': 'success',
            'message': f'Started reprocessing failed documents (batch size: {batch_size}, delay: {delay_seconds}s)',
            'task_id': task.id
        })
    except Exception as e:
        current_app.logger.error(f"Error reprocessing failed documents: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
        
@main_routes.route('/api/reprocess-document/<int:document_id>', methods=['POST'])
def reprocess_document(document_id):
    """API endpoint to reprocess a specific document by ID"""
    try:
        from tasks.recovery_tasks import reprocess_specific_document
        
        # Start the task
        task = reprocess_specific_document.delay(document_id)
        
        return jsonify({
            'status': 'success',
            'message': f'Started reprocessing document ID: {document_id}',
            'task_id': task.id
        })
    except Exception as e:
        current_app.logger.error(f"Error reprocessing document {document_id}: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500





@main_routes.route('/metrics-dashboard')
def metrics_dashboard():
    """Dashboard for system KPIs and metrics"""
    try:
        from app.models.models import Document, LLMAnalysis, Classification, ExtractedText
        
        # Time period for metrics (default: last 30 days)
        days = request.args.get('days', 30, type=int)
        time_period = datetime.utcnow() - timedelta(days=days)
        
        # Base query for recent documents
        base_query = Document.query.filter(Document.upload_date >= time_period)
        total_docs = base_query.count()
        
        # Document processing metrics
        start_time = time.time()
        
        metrics = {
            'document_counts': {},
            'processing_times': {},
            'confidence_scores': {},
            'daily_processing': [],
            'file_types': {},
            'processing_success_rate': 0
        }
        
        # Calculate processing counts
        metrics['document_counts'] = {
            'total': total_docs,
            'completed': base_query.filter(Document.status == 'COMPLETED').count(),
            'failed': base_query.filter(Document.status == 'FAILED').count(),
            'pending': base_query.filter(Document.status == 'PENDING').count(),
            'processing': base_query.filter(Document.status == 'PROCESSING').count()
        }
        
        # Calculate success rate
        if total_docs > 0:
            metrics['processing_success_rate'] = (metrics['document_counts']['completed'] / total_docs) * 100
        
        # Document processing times
        # This requires adding processing_time field to Document or calculating from logs
        # Estimate based on document metadata
        
        # Confidence scores for different components
        confidence_query = db.session.query(
            func.avg(LLMAnalysis.confidence_score).label('llm_confidence'),
            func.avg(Classification.confidence).label('classification_confidence'),
            func.avg(ExtractedText.confidence).label('extraction_confidence')
        ).join(
            Classification, Classification.document_id == LLMAnalysis.document_id, isouter=True
        ).join(
            ExtractedText, ExtractedText.document_id == LLMAnalysis.document_id, isouter=True
        ).filter(
            LLMAnalysis.analysis_date >= time_period
        ).first()
        
        metrics['confidence_scores'] = {
            'text_extraction': round((confidence_query.extraction_confidence or 0) * 100, 2),
            'classification': round((confidence_query.classification_confidence or 0), 2),
            'llm_analysis': round((confidence_query.llm_confidence or 0) * 100, 2)
        }
        
        # Get file types distribution
        file_extensions = db.session.query(
            func.lower(func.substring(Document.filename, func.length(Document.filename) - 3, 4)).label('extension'),
            func.count().label('count')
        ).filter(
            Document.upload_date >= time_period
        ).group_by(
            text('extension')
        ).all()

        # Convert to a Python dictionary explicitly
        metrics['file_types'] = {ext: count for ext, count in file_extensions}

        # Calculate query time for metrics
        metrics['metrics_query_time'] = round((time.time() - start_time) * 1000, 2)  # in ms

        # Add convenience keys for templates
        metrics['file_type_keys'] = list(metrics['file_types'].keys())
        metrics['file_type_values'] = list(metrics['file_types'].values())

        # Debug output
        print("Metrics keys:", metrics.keys())
        for key, value in metrics.items():
            print(f"{key}: {type(value)}")
        
        # Daily document processing volume
        daily_processing = db.session.query(
            func.date(Document.upload_date).label('date'),
            func.count().label('total'),
            func.sum(case((Document.status == 'COMPLETED', 1), else_=0)).label('completed'),
            func.sum(case((Document.status == 'FAILED', 1), else_=0)).label('failed')
        ).filter(
            Document.upload_date >= time_period
        ).group_by(
            text('date')
        ).order_by(
            text('date')
        ).all()
        
        metrics['daily_processing'] = [
            {
                'date': date.strftime('%Y-%m-%d'),
                'total': total,
                'completed': completed,
                'failed': failed,
                'success_rate': (completed / total * 100) if total > 0 else 0
            }
            for date, total, completed, failed in daily_processing
        ]
        
        # Estimate search response time (placeholder)
        metrics['search_response_time'] = "< 500ms"  # This is a placeholder
        
        # Average PDF processing time (placeholder - would need timing data)
        metrics['processing_times'] = {
            'pdf': "~10-15 seconds",
            'image': "~5-10 seconds",
            'average': "~12 seconds"
        }
        
        # Calculate query time for metrics
        print(f"metrics['file_types'] type: {type(metrics['file_types'])}")


        print("Metrics keys:", metrics.keys())
        for key, value in metrics.items():
            print(f"{key}: {type(value)}")
        
        return render_template('pages/metrics.html', 
                              metrics=metrics,
                              days=days)
        
    except Exception as e:
        current_app.logger.error(f"Error generating metrics: {str(e)}")
        flash(f"Error generating metrics: {str(e)}", "error")
        return redirect(url_for('main_routes.index'))


@main_routes.route('/api/search-metrics')
def search_metrics():
    """Return metrics about search performance"""
    global search_times
    
    if not search_times:
        return jsonify({
            'avg_response_time': 0,
            'count': 0,
            'min_response_time': 0,
            'max_response_time': 0,
            'recent_response_times': []
        })
    
    # Calculate metrics
    avg_time = mean(search_times)
    min_time = min(search_times)
    max_time = max(search_times)
    
    # Get the most recent 10 times
    recent_times = search_times[-10:]
    
    return jsonify({
        'avg_response_time': round(avg_time, 2),
        'count': len(search_times),
        'min_response_time': round(min_time, 2),
        'max_response_time': round(max_time, 2),
        'recent_response_times': [round(t, 2) for t in recent_times]
    })

# Update your metrics_dashboard function to include search response time
def get_search_response_time():
    """Get the average search response time for metrics"""
    global search_times
    
    if not search_times:
        return "No data"
    
    avg_time = mean(search_times)
    return f"{round(avg_time, 2)} ms"



#RECOVERY ROUTES



@main_routes.route('/recovery-dashboard')
def recovery_dashboard():
    """View to display failed documents and recovery options"""
    try:
        # Get counts for different statuses
        from app.models.models import Document
        from tasks.utils import TASK_STATUSES
        
        status_counts = {}
        total_docs = Document.query.count()
        
        for status_name, status_value in TASK_STATUSES.items():
            count = Document.query.filter_by(status=status_value).count()
            status_counts[status_name] = count
        
        # Get the most recent failed documents
        failed_docs = Document.query.filter_by(status='FAILED').order_by(Document.upload_date.desc()).limit(10).all()
        
        formatted_failed_docs = []
        for doc in failed_docs:
            formatted_failed_docs.append({
                'id': doc.id,
                'filename': doc.filename,
                'upload_date': doc.upload_date.strftime('%Y-%m-%d %H:%M:%S'),
                'file_size': doc.file_size
            })
        
        return render_template(
            'recovery.html',
            total_docs=total_docs,
            status_counts=status_counts,
            failed_docs=formatted_failed_docs
        )
    except Exception as e:
        current_app.logger.error(f"Error loading recovery dashboard: {str(e)}", exc_info=True)
        flash(f"Error loading recovery dashboard: {str(e)}", "error")
        return redirect(url_for('main_routes.index'))


@main_routes.route('/admin/recover-pending', methods=['GET', 'POST'])
def recover_pending_documents():
    """Admin route to recover documents stuck in PENDING state"""
    if request.method == 'POST':
        action = request.form.get('action')
        document_ids = request.form.getlist('document_ids')
        
        if not document_ids:
            flash('No documents selected', 'error')
            return redirect(url_for('main_routes.recover_pending_documents'))
            
        count = 0
        
        # Convert string IDs to integers
        doc_ids = [int(doc_id) for doc_id in document_ids if doc_id.isdigit()]
        
        if action == 'retry':
            # Reprocess selected documents
            for doc_id in doc_ids:
                doc = Document.query.get(doc_id)
                if doc and doc.status == 'PENDING':
                    # Queue for reprocessing with the document task
                    try:
                        minio_path = f"{storage.bucket}/{doc.filename}"
                        current_app.logger.info(f"Reprocessing document {doc.id}: {doc.filename}")
                        
                        # Explicitly import process_document
                        from tasks.document_tasks import process_document
                        task = process_document.delay(doc.filename, minio_path, doc.id)
                        
                        current_app.logger.info(f"Reprocessing task queued with ID: {task.id}")
                        count += 1
                    except Exception as e:
                        current_app.logger.error(f"Error reprocessing document {doc.id}: {str(e)}")
            
            flash(f'Requeued {count} documents for processing', 'success')
            
        elif action == 'fail':
            # Mark selected documents as failed
            for doc_id in doc_ids:
                doc = Document.query.get(doc_id)
                if doc and doc.status == 'PENDING':
                    doc.status = 'FAILED'
                    count += 1
            
            db.session.commit()
            flash(f'Marked {count} documents as FAILED', 'success')
            
        elif action == 'delete':
            # Delete selected documents
            for doc_id in doc_ids:
                doc = Document.query.get(doc_id)
                if doc and doc.status == 'PENDING':
                    # Delete related records
                    LLMKeyword.query.filter(LLMKeyword.llm_analysis_id.in_(
                        db.session.query(LLMAnalysis.id).filter_by(document_id=doc.id)
                    )).delete(synchronize_session=False)
                    LLMAnalysis.query.filter_by(document_id=doc.id).delete()
                    Classification.query.filter_by(document_id=doc.id).delete()
                    DesignElement.query.filter_by(document_id=doc.id).delete()
                    ExtractedText.query.filter_by(document_id=doc.id).delete()
                    DropboxSync.query.filter_by(document_id=doc.id).delete()
                    
                    # Try to delete from MinIO
                    try:
                        storage.client.remove_object(storage.bucket, doc.filename)
                    except Exception as e:
                        current_app.logger.warning(f"Failed to remove object from MinIO: {str(e)}")
                    
                    # Delete document record
                    db.session.delete(doc)
                    count += 1
            
            db.session.commit()
            flash(f'Deleted {count} documents', 'success')
        
        return redirect(url_for('main_routes.recover_pending_documents'))
    
    # Get pending documents
    pending_docs = Document.query.filter_by(status='PENDING').all()
    
    return render_template(
        'recover_pending.html', 
        documents=pending_docs,
        count=len(pending_docs)
    )