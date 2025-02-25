# app/routes/main_routes.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from app.services.storage_service import MinIOStorage
from app.extensions import db
from app.models.models import Document, LLMAnalysis, LLMKeyword
from sqlalchemy import or_
from app.services.preview_service import PreviewService
from app.services.dropbox_service import DropboxService
from flask_wtf.csrf import generate_csrf
from app import csrf

main_routes = Blueprint('main_routes', __name__)
storage = MinIOStorage()
preview_service = PreviewService()

def get_celery_task(task_name):
    """Lazy import of celery tasks to avoid circular imports"""
    if task_name == 'process_document':
        from tasks.document_tasks import process_document
        return process_document
    elif task_name == 'sync_dropbox':
        from tasks.dropbox_tasks import sync_dropbox
        return sync_dropbox

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
        
        document = Document(
            filename=filename,
            upload_date=datetime.utcnow(),
            file_size=os.path.getsize(temp_path),
            status='PENDING',
            page_count=1
        )
        db.session.add(document)
        db.session.commit()

        minio_path = storage.upload_file(temp_path, filename)
        
        # Get process_document task
        process_document = get_celery_task('process_document')
        process_document.delay(filename, minio_path, document.id)
        
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
            
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(results)
        
        return render_template('pages/search.html', documents=results, query=query)
        
    except Exception as e:
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
        failed_docs = Document.query.filter_by(status=TASK_STATUSES['FAILED']).order_by(Document.upload_date.desc()).limit(10).all()
        
        formatted_failed_docs = []
        for doc in failed_docs:
            formatted_failed_docs.append({
                'id': doc.id,
                'filename': doc.filename,
                'upload_date': doc.upload_date.strftime('%Y-%m-%d %H:%M:%S'),
                'file_size': doc.file_size
            })
        
        return render_template(
            'pages/recovery.html',
            total_docs=total_docs,
            status_counts=status_counts,
            failed_docs=formatted_failed_docs
        )
    except Exception as e:
        current_app.logger.error(f"Error loading recovery dashboard: {str(e)}")
        flash(f"Error loading recovery dashboard: {str(e)}", "error")
        return redirect(url_for('main_routes.index'))