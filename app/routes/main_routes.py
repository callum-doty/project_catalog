# app/routes/main_routes.py

from flask import Blueprint, render_template, request, session, flash, redirect, url_for, jsonify, current_app
from werkzeug.utils import secure_filename
import os
import app
from sqlalchemy.orm import joinedload
from datetime import datetime
from app.services.storage_service import MinIOStorage
from app.extensions import db
from app.models.models import Document, LLMAnalysis, LLMKeyword, Classification, DesignElement, ExtractedText, DropboxSync, Entity, CommunicationFocus
from app.models.keyword_models import KeywordTaxonomy, KeywordSynonym, DocumentKeyword
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
from tasks.dropbox_tasks import sync_dropbox
from functools import wraps
from app.extensions import cache
from app.services.document_service import get_document_count, get_document_counts_by_status
from flask_caching import Cache
from app.utils import search_with_timeout, document_has_column, monitor_query




main_routes = Blueprint('main_routes', __name__)
storage = MinIOStorage()
preview_service = PreviewService()
search_times = []
MAX_SEARCH_TIMES = 100


def check_password(password):
    """Check if the password is valid"""
    correct_password = os.environ.get('SITE_PASSWORD', 'your_secure_password')
    return password == correct_password

def password_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check if user is already authenticated
        if session.get('authenticated'):
            return f(*args, **kwargs)
        
        # Check if password was submitted
        if request.method == 'POST' and 'password' in request.form:
            if check_password(request.form['password']):
                session['authenticated'] = True
                return redirect(url_for('main_routes.search_documents'))
            else:
                return render_template('password.html', error='Incorrect password')
        
        # Show password form
        return render_template('password.html')
    return decorated

# Protect all routes in this blueprint
@main_routes.before_request
def protect_blueprint():
    # Add debug logging
    current_app.logger.info(f"Accessing route: {request.endpoint} with method {request.method}")
    
    # Skip authentication for certain endpoints
    if request.endpoint in ['main_routes.static', 'main_routes.password_check']:
        return None
    
    # Check if authenticated
    if not session.get('authenticated'):
        # Preserve the requested URL as 'next' parameter
        next_url = request.url
        return redirect(url_for('main_routes.password_check', next=next_url))
    
    return None

# Add a route to handle password submission
@main_routes.route('/password-check', methods=['GET', 'POST'])
def password_check():
    # For debugging - log the request method
    current_app.logger.info(f"Password check accessed with method: {request.method}")
    
    # Handle POST requests directly
    if request.method == 'POST':
        if 'password' in request.form:
            if check_password(request.form['password']):
                session['authenticated'] = True
                # Use relative URL for redirection
                next_url = request.args.get('next') or url_for('main_routes.search_documents')
                return redirect(next_url)
            else:
                return render_template('password.html', error='Incorrect password')
    
    # For GET requests, show the password form
    return render_template('password.html')

#end password section

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
    # Redirect to the search page instead of showing the index page
    return redirect(url_for('main_routes.search_documents'))

@main_routes.route('/dashboard')
@monitor_query
def dashboard():
    document_counts = get_document_counts_by_status()
    return render_template('dashboard.html', counts=document_counts)

@main_routes.route('/home')
def home():
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
        return redirect(url_for('main_routes.search_documents'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('main_routes.search_documents'))

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

        # Queue document processing
        try:
            current_app.logger.info(f"Queuing document {document.id} for processing")

            from tasks.document_tasks import process_document
            task = process_document.delay(filename, minio_path, document.id)
            current_app.logger.info(f"Task queued with ID: {task.id}")

            from tasks.preview_tasks import generate_preview
            preview_task = generate_preview.delay(filename, document.id)
            current_app.logger.info(f"Preview task queued with ID: {preview_task.id}")

        except Exception as e:
            current_app.logger.error(f"Failed to queue tasks for document: {str(e)}")
        
        os.remove(temp_path)
        flash('File uploaded successfully', 'success')
        return redirect(url_for('main_routes.search_documents'))

    except Exception as e:
        current_app.logger.error(f"Upload error: {str(e)}")
        flash(f'Error uploading file: {str(e)}', 'error')
        return redirect(url_for('main_routes.search_documents'))
    
    
@main_routes.route('/search')
def search_documents():
    """Redirect to the search route"""
    return redirect(url_for('search_routes.search_documents', **request.args))


# Helper function to get hierarchical keywords for a document
@cache.memoize(timeout=300)
def get_document_hierarchical_keywords(document_id):
    """Get hierarchical keywords for a document"""
    try:
        from app.models.keyword_models import DocumentKeyword, KeywordTaxonomy
        
        keywords = db.session.query(
            DocumentKeyword, KeywordTaxonomy
        ).join(
            KeywordTaxonomy, DocumentKeyword.taxonomy_id == KeywordTaxonomy.id
        ).filter(
            DocumentKeyword.document_id == document_id
        ).all()
        
        # Format keywords for display
        result = []
        for doc_kw, taxonomy in keywords:
            result.append({
                'id': taxonomy.id,
                'term': taxonomy.term,
                'primary_category': taxonomy.primary_category,
                'subcategory': taxonomy.subcategory,
                'relevance_score': doc_kw.relevance_score
            })
        
        return result
    except Exception as e:
        current_app.logger.error(f"Error getting hierarchical keywords: {str(e)}")
        return []

# Generate taxonomy facets for sidebar
@cache.memoize(timeout=300)
def generate_taxonomy_facets(selected_primary=None, selected_subcategory=None):
    """Generate taxonomy facets for sidebar filtering"""
    try:
        # Create a CTE for documents that have keywords
        docs_with_keywords = db.session.query(
            DocumentKeyword.taxonomy_id, 
            func.count(DocumentKeyword.document_id.distinct()).label('doc_count')
        ).group_by(
            DocumentKeyword.taxonomy_id
        ).cte('docs_with_keywords')
        
        # Get primary categories with counts
        primary_categories = db.session.query(
            KeywordTaxonomy.primary_category,
            func.sum(docs_with_keywords.c.doc_count).label('count')
        ).join(
            docs_with_keywords, KeywordTaxonomy.id == docs_with_keywords.c.taxonomy_id
        ).group_by(
            KeywordTaxonomy.primary_category
        ).order_by(
            KeywordTaxonomy.primary_category
        ).all()
        
        # If a primary category is selected, get subcategories
        subcategories = []
        if selected_primary:
            subcategories = db.session.query(
                KeywordTaxonomy.subcategory,
                func.count(KeywordTaxonomy.id.distinct()).label('count')
            ).filter(
                KeywordTaxonomy.primary_category == selected_primary
            ).join(
                DocumentKeyword, KeywordTaxonomy.id == DocumentKeyword.taxonomy_id
            ).group_by(
                KeywordTaxonomy.subcategory
            ).order_by(
                KeywordTaxonomy.subcategory
            ).all()
        
        # Format results
        result = {
            'primary_categories': [
                {'name': cat, 'count': count, 'selected': cat == selected_primary}
                for cat, count in primary_categories
            ],
            'subcategories': [
                {'name': subcat, 'count': count, 'selected': subcat == selected_subcategory}
                for subcat, count in subcategories
            ] if selected_primary else []
        }
        
        return result
    except Exception as e:
        current_app.logger.error(f"Error generating taxonomy facets: {str(e)}")
        return {'primary_categories': [], 'subcategories': []}


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
        return redirect(url_for('main_routes.search_documents'))


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


@main_routes.route('/recovery-dashboard')
def recovery_dashboard():
    """Display failed documents for recovery"""
    try:
        # Get all documents with FAILED status
        failed_documents = Document.query.filter_by(status='FAILED').order_by(Document.upload_date.desc()).all()
        
        # Prepare data for template
        documents_data = []
        
        for doc in failed_documents:
            preview = None
            try:
                preview = preview_service.get_preview(doc.filename)
            except Exception as e:
                current_app.logger.error(f"Preview generation failed for {doc.filename}: {str(e)}")
            
            documents_data.append({
                'id': doc.id,
                'filename': doc.filename,
                'upload_date': doc.upload_date.strftime('%Y-%m-%d %H:%M:%S'),
                'file_size': f"{(doc.file_size/1024):.2f} KB",
                'preview': preview,
                'status': doc.status
            })
        
        return render_template('pages/recovery.html', documents=documents_data)
        
    except Exception as e:
        current_app.logger.error(f"Error in recovery dashboard: {str(e)}", exc_info=True)
        flash(f'Error loading recovery dashboard: {str(e)}', 'error')
        return render_template('pages/recovery.html', documents=[])


@main_routes.route('/admin/recover-pending')
def recover_pending():
    """Display pending documents that might be stuck for recovery"""
    try:
        # Get all documents with PENDING or PROCESSING status
        pending_documents = Document.query.filter(
            Document.status.in_(['PENDING', 'PROCESSING'])
        ).order_by(Document.upload_date.desc()).all()
        
        # Prepare data for template
        documents_data = []
        
        for doc in pending_documents:
            # Calculate time since upload - handle timezone-aware dates correctly
            if doc.upload_date.tzinfo:
                # If doc.upload_date is timezone-aware, make utcnow timezone-aware too
                from datetime import timezone
                current_time = datetime.utcnow().replace(tzinfo=timezone.utc)
            else:
                # If doc.upload_date is naive, use naive utcnow
                current_time = datetime.utcnow()
                
            time_since_upload = current_time - doc.upload_date
            hours_pending = time_since_upload.total_seconds() / 3600
            
            # Only show documents that have been pending for more than 1 hour
            if hours_pending < 1:
                continue
                
            preview = None
            try:
                preview = preview_service.get_preview(doc.filename)
            except Exception as e:
                current_app.logger.error(f"Preview generation failed for {doc.filename}: {str(e)}")
            
            documents_data.append({
                'id': doc.id,
                'filename': doc.filename,
                'upload_date': doc.upload_date.strftime('%Y-%m-%d %H:%M:%S'),
                'file_size': f"{(doc.file_size/1024):.2f} KB",
                'preview': preview,
                'status': doc.status,
                'hours_pending': round(hours_pending, 1)
            })
        
        return render_template('pages/recover_pending.html', documents=documents_data)
        
    except Exception as e:
        current_app.logger.error(f"Error in recover pending: {str(e)}", exc_info=True)
        flash(f'Error loading recover pending dashboard: {str(e)}', 'error')
        return render_template('pages/recover_pending.html', documents=[])


@main_routes.route('/api/recover-document/<int:document_id>', methods=['POST'])
def recover_document(document_id):
    """Trigger reprocessing of a failed document"""
    try:
        document = Document.query.get_or_404(document_id)
        
        if document.status not in ['FAILED', 'PENDING', 'PROCESSING']:
            return jsonify({
                'status': 'error',
                'message': f'Document is not in a recoverable state: {document.status}'
            }), 400
        
        # Import recovery task
        from tasks.recovery_tasks import reprocess_document
        
        # Reset document status
        document.status = 'PENDING'
        db.session.commit()
        
        # Get the file from MinIO storage
        minio_path = f"{storage.bucket}/{document.filename}"
        
        # Queue reprocessing task
        task = reprocess_document.delay(document.filename, minio_path, document.id)
        
        return jsonify({
            'status': 'success',
            'message': f'Document recovery initiated for {document.filename}',
            'task_id': task.id
        })
        
    except Exception as e:
        current_app.logger.error(f"Error recovering document: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@main_routes.route('/api/recovery-status/<int:document_id>', methods=['GET'])
def recovery_status(document_id):
    """Get current status of a document"""
    try:
        document = Document.query.get_or_404(document_id)
        
        return jsonify({
            'status': 'success',
            'document_status': document.status,
            'id': document.id,
            'filename': document.filename
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting recovery status: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@main_routes.route('/api/execute-sync', methods=['POST'])
def execute_sync():
    """Directly execute Dropbox sync (not just queue it)"""
    try:
        current_app.logger.info("Directly executing Dropbox sync")
        
        # Import the sync task function
        from tasks.dropbox_tasks import sync_dropbox
        
        # Call the function directly (not as a task)
        result = sync_dropbox()
        
        return jsonify({
            'status': 'success',
            'message': 'Sync executed directly',
            'result': result
        })
    except Exception as e:
        current_app.logger.error(f"Error executing sync: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@main_routes.route('/api/cache-stats')
def cache_stats():
    """Return basic cache statistics"""
    stats = {
        'cache_type': app.config['CACHE_TYPE'],
        'default_timeout': app.config['CACHE_DEFAULT_TIMEOUT'],
    }
    
    # Add Redis-specific stats if using Redis
    if app.config['CACHE_TYPE'] == 'redis':
        try:
            import redis
            redis_client = redis.from_url(app.config['CACHE_REDIS_URL'])
            info = redis_client.info()
            stats.update({
                'connected_clients': info.get('connected_clients', 0),
                'used_memory_human': info.get('used_memory_human', 'N/A'),
                'hit_rate': info.get('keyspace_hits', 0) / 
                           (info.get('keyspace_hits', 0) + info.get('keyspace_misses', 0) + 0.001),
                'total_keys': sum(db.get('keys', 0) for db in info.get('keyspace', {}).values()),
            })
        except Exception as e:
            stats['error'] = str(e)
    
    return jsonify(stats)


@main_routes.route('/api/preview-status/<path:filename>')
def preview_status(filename):
    """Check if a preview is available in cache"""
    cache_key = f"preview:{filename}"
    preview_data = cache.get(cache_key)
    
    if preview_data:
        return jsonify({
            'status': 'available',
            'preview_url': preview_data
        })
    else:
        # Check if still in progress
        in_progress = cache.get(f"preview_in_progress:{filename}")
        return jsonify({
            'status': 'pending' if in_progress else 'not_found'
        })

def get_document_hierarchical_keywords_bulk(document_ids):
    """Efficiently get hierarchical keywords for multiple documents at once"""
    try:
        keywords_data = db.session.query(
            DocumentKeyword.document_id, 
            KeywordTaxonomy.id,
            KeywordTaxonomy.term,
            KeywordTaxonomy.primary_category,
            KeywordTaxonomy.subcategory,
            DocumentKeyword.relevance_score
        ).join(
            KeywordTaxonomy, DocumentKeyword.taxonomy_id == KeywordTaxonomy.id
        ).filter(
            DocumentKeyword.document_id.in_(document_ids)
        ).all()
        
        results = {doc_id: [] for doc_id in document_ids}
        
        for doc_id, tax_id, term, primary_cat, subcat, score in keywords_data:
            results[doc_id].append({
                'id': tax_id,
                'term': term,
                'primary_category': primary_cat,
                'subcategory': subcat,
                'relevance_score': score
            })
        
        return results
    except Exception as e:
        current_app.logger.error(f"Error getting hierarchical keywords: {str(e)}")
        return {doc_id: [] for doc_id in document_ids}



@main_routes.route('/api/documents')
def api_documents():
    last_id = request.args.get('last_id', type=int)
    limit = request.args.get('limit', 20, type=int)
    
    query = Document.query.order_by(Document.id)
    
    if last_id:
        # Keyset pagination - much more efficient for large tables
        query = query.filter(Document.id > last_id)
    
    documents = query.limit(limit).all()
    
    return jsonify({
        'documents': [doc.to_dict() for doc in documents],
        'has_more': len(documents) == limit,
        'last_id': documents[-1].id if documents else None
    })


# Add to app/routes/main_routes.py

@main_routes.route('/api/preview/<path:filename>')
def get_document_preview(filename):
    """API endpoint for fetching document previews"""
    try:
        preview = preview_service.get_preview(filename)
        return jsonify({
            'status': 'success',
            'preview': preview
        })
    except Exception as e:
        current_app.logger.error(f"Preview API error for {filename}: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 404


@main_routes.route('/api/sync-status')
def sync_status():
    """API endpoint to check sync status"""
    try:
        # Check if DropboxService is available
        try:
            from app.services.dropbox_service import DropboxService
            dropbox_service = DropboxService()
            status = dropbox_service.get_sync_status()
        except ImportError:
            # If Dropbox service not available, return dummy data
            status = {
                'dropbox_connected': False,
                'last_sync_time': None,
                'last_status': 'NOT_CONFIGURED',
                'message': 'Dropbox integration not configured'
            }
            
        return jsonify(status)
    except Exception as e:
        current_app.logger.error(f"Error checking sync status: {str(e)}")
        return jsonify({
            'error': str(e),
            'dropbox_connected': False
        }), 500