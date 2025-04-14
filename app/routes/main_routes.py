# app/routes/main_routes.py

from flask import Blueprint, render_template, request, session, flash, redirect, url_for, jsonify, current_app
from werkzeug.utils import secure_filename
import os
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
        return redirect(url_for('main_routes.search_documents'))

    except Exception as e:
        current_app.logger.error(f"Upload error: {str(e)}")
        flash(f'Error uploading file: {str(e)}', 'error')
        return redirect(url_for('main_routes.search_documents'))



def cached_view(timeout=60, query_string=False):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            cache = current_app.extensions["cache"].get(Cache)
            return cache.cached(timeout=timeout, query_string=query_string)(fn)(*args, **kwargs)
        return wrapper
    return decorator


@main_routes.route('/search')
@cache.cached(timeout=60, query_string=True)
def search_documents():
    """Search implementation with full-text search capability"""
    # Get search parameters from request
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 12, type=int)
    sort_by = request.args.get('sort_by', 'upload_date')
    sort_direction = request.args.get('sort_dir', 'desc')
    
    # Filter parameters
    filter_type = request.args.get('filter_type', '')
    filter_year = request.args.get('filter_year', '')
    filter_location = request.args.get('filter_location', '')
    
    # Taxonomy filter parameters
    primary_category = request.args.get('primary_category', '')
    subcategory = request.args.get('subcategory', '')
    
    start_time = time.time()  # Start timing
    
    # Initialize variables that might be used in the error handler
    taxonomy_facets = {'primary_categories': [], 'subcategories': []}
    taxonomy_terms = []
    
    try:
        # Initialize base query
        document_ids_query = db.session.query(Document.id)
        
        # Apply full-text search if query is provided
        if query:
            # Try to find matching taxonomy terms
            taxonomy_terms = KeywordTaxonomy.query.filter(
                KeywordTaxonomy.term.ilike(f'%{query}%')
            ).limit(5).all()
            
            # Full-text search using search vectors if they exist
            # Check if the search_vector column exists
            has_search_vector = False
            try:
                Document.search_vector
                has_search_vector = True
            except AttributeError:
                # Fallback to traditional search if search_vector doesn't exist
                pass
                
            if has_search_vector:
                # Convert search query to tsquery format
                tsquery = func.plainto_tsquery('english', query)
                
                # Subquery for documents matching with full-text search
                doc_matches = db.session.query(Document.id).filter(
                    Document.search_vector.op('@@')(tsquery)
                ).subquery()
                
                # Subquery for LLM Analysis matches
                llm_matches = db.session.query(LLMAnalysis.document_id).filter(
                    LLMAnalysis.search_vector.op('@@')(tsquery)
                ).subquery()
                
                # Subquery for Extracted Text matches
                text_matches = db.session.query(ExtractedText.document_id).filter(
                    ExtractedText.search_vector.op('@@')(tsquery)
                ).subquery()
                
                # Combine all matches
                document_ids_query = document_ids_query.filter(
                    or_(
                        Document.id.in_(doc_matches),
                        Document.id.in_(llm_matches),
                        Document.id.in_(text_matches)
                    )
                )
            else:
                # Fallback to traditional search with ILIKE
                document_ids_query = document_ids_query.outerjoin(
                    LLMAnalysis, Document.id == LLMAnalysis.document_id
                ).outerjoin(
                    LLMKeyword, LLMAnalysis.id == LLMKeyword.llm_analysis_id
                ).outerjoin(
                    ExtractedText, Document.id == ExtractedText.document_id
                ).filter(
                    or_(
                        Document.filename.ilike(f'%{query}%'),
                        LLMAnalysis.summary_description.ilike(f'%{query}%'),
                        LLMKeyword.keyword.ilike(f'%{query}%'),
                        ExtractedText.main_message.ilike(f'%{query}%')
                    )
                )
        
        # Apply other filters
        if filter_type:
            type_matches = db.session.query(LLMAnalysis.document_id).filter(
                LLMAnalysis.document_tone == filter_type
            ).subquery()
            document_ids_query = document_ids_query.filter(Document.id.in_(type_matches))
                
        if filter_year:
            year_matches = db.session.query(LLMAnalysis.document_id).filter(
                LLMAnalysis.election_year == filter_year
            ).subquery()
            document_ids_query = document_ids_query.filter(Document.id.in_(year_matches))
                
        if filter_location:
            loc_matches = db.session.query(DesignElement.document_id).filter(
                func.lower(DesignElement.geographic_location).like(f"%{filter_location.lower()}%")
            ).subquery()
            document_ids_query = document_ids_query.filter(Document.id.in_(loc_matches))
        
        # Apply taxonomy filters
        if primary_category:
            taxonomy_matches = db.session.query(DocumentKeyword.document_id).join(
                KeywordTaxonomy, DocumentKeyword.taxonomy_id == KeywordTaxonomy.id
            ).filter(
                KeywordTaxonomy.primary_category == primary_category
            )
            
            if subcategory:
                taxonomy_matches = taxonomy_matches.filter(
                    KeywordTaxonomy.subcategory == subcategory
                )
                
            taxonomy_matches = taxonomy_matches.subquery()
            document_ids_query = document_ids_query.filter(Document.id.in_(taxonomy_matches))
        
        if sort_by == 'filename':
            if sort_direction == 'desc':
                document_ids_query = document_ids_query.order_by(Document.filename.desc())
            else:
                document_ids_query = document_ids_query.order_by(Document.filename)
        else:  # Default to sort by upload date
            if sort_direction == 'desc':
                document_ids_query = document_ids_query.order_by(Document.upload_date.desc())
            else:
                document_ids_query = document_ids_query.order_by(Document.upload_date)
        
        # Get total count for pagination before applying limit/offset
        total_count = document_ids_query.count()
        
        # Apply pagination at the database level
        document_ids = document_ids_query.offset((page - 1) * per_page).limit(per_page).all()
        document_ids = [doc_id for (doc_id,) in document_ids]  # Extract IDs from result tuples
        
        # Now fetch only the necessary documents with all required relationships
        if document_ids:
            documents = Document.query.filter(
                Document.id.in_(document_ids)
            ).options(
                # Eager loading of relationships
                joinedload(Document.llm_analysis),
                joinedload(Document.entity),
                joinedload(Document.design_elements),
                joinedload(Document.communication_focus),
                joinedload(Document.extracted_text)
            ).all()
            
            # Sort the results to match the order from the ID query
            id_order_map = {id: index for index, id in enumerate(document_ids)}
            documents.sort(key=lambda doc: id_order_map.get(doc.id, 0))
        else:
            documents = []
        
        # Create pagination object
        pagination = {
            'page': page,
            'per_page': per_page,
            'total': total_count,
            'pages': (total_count + per_page - 1) // per_page,  # Ceiling division
            'has_prev': page > 1,
            'has_next': page < ((total_count + per_page - 1) // per_page),
            'prev_page': page - 1 if page > 1 else None,
            'next_page': page + 1 if page < ((total_count + per_page - 1) // per_page) else None
        }
        
        # Format results
        results = []
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
                'summary': doc.llm_analysis.summary_description if hasattr(doc, 'llm_analysis') and doc.llm_analysis else '',
                'keywords': [],
                
                # Add new fields from models
                'document_type': doc.llm_analysis.campaign_type if hasattr(doc, 'llm_analysis') and doc.llm_analysis else '',
                'election_year': doc.llm_analysis.election_year if hasattr(doc, 'llm_analysis') and doc.llm_analysis else '',
                'document_tone': doc.llm_analysis.document_tone if hasattr(doc, 'llm_analysis') and doc.llm_analysis else '',
                
                'client': doc.entity.client_name if hasattr(doc, 'entity') and doc.entity else '',
                'opponent': doc.entity.opponent_name if hasattr(doc, 'entity') and doc.entity else '',
                
                'location': doc.design_elements.geographic_location if hasattr(doc, 'design_elements') and doc.design_elements else '',
                'target_audience': doc.design_elements.target_audience if hasattr(doc, 'design_elements') and doc.design_elements else '',
                
                'primary_issue': doc.communication_focus.primary_issue if hasattr(doc, 'communication_focus') and doc.communication_focus else '',
                
                'main_message': doc.extracted_text.main_message if hasattr(doc, 'extracted_text') and doc.extracted_text else '',
                
                # Add hierarchical keywords for each document
                'hierarchical_keywords': get_document_hierarchical_keywords(doc.id)
            }
            
            # Add keywords if they exist
            if hasattr(doc, 'llm_analysis') and doc.llm_analysis and hasattr(doc.llm_analysis, 'keywords'):
                formatted_doc['keywords'] = [
                    {
                        'text': kw.keyword,
                        'category': kw.category
                    } for kw in doc.llm_analysis.keywords if hasattr(kw, 'keyword')
                ]
            
            results.append(formatted_doc)
            
        # Generate taxonomy facets for filtering
        taxonomy_facets = generate_taxonomy_facets(primary_category, subcategory)
        
        # Record search time
        response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        record_search_time(response_time)
        
        # Get filter options
        filter_options = {
            'document_types': db.session.query(LLMAnalysis.document_tone, func.count(LLMAnalysis.document_tone))
                .group_by(LLMAnalysis.document_tone).all(),
            'years': db.session.query(LLMAnalysis.election_year, func.count(LLMAnalysis.election_year))
                .group_by(LLMAnalysis.election_year).all(),
            'locations': db.session.query(DesignElement.geographic_location, func.count(DesignElement.geographic_location))
                .group_by(DesignElement.geographic_location).all()
        }
        
        # Return response
        return render_template(
            'pages/search.html', 
            documents=results, 
            query=query,
            pagination=pagination,
            sort_by=sort_by,
            sort_dir=sort_direction,
            filter_options=filter_options,
            filter_type=filter_type,
            filter_year=filter_year,
            filter_location=filter_location,
            primary_category=primary_category,
            subcategory=subcategory,
            response_time_ms=round(response_time, 2),
            taxonomy_facets=taxonomy_facets,
            matching_terms=taxonomy_terms
        )
        
    except Exception as e:
        # Error handling
        response_time = (time.time() - start_time) * 1000
        record_search_time(response_time)
        
        current_app.logger.error(f"Search error: {str(e)}", exc_info=True)
        return render_template(
            'pages/search.html', 
            documents=[], 
            query=query, 
            error=str(e),
            taxonomy_facets=taxonomy_facets  
        )


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
        from app.models.keyword_models import KeywordTaxonomy, DocumentKeyword
        
        # Get primary categories with counts
        primary_categories = db.session.query(
            KeywordTaxonomy.primary_category,
            func.count(KeywordTaxonomy.id.distinct()).label('count')
        ).join(
            DocumentKeyword, KeywordTaxonomy.id == DocumentKeyword.taxonomy_id
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