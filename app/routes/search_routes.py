# app/routes/search_routes.py

from flask import Blueprint, render_template, request, jsonify, current_app, flash
from sqlalchemy import or_, func, desc, asc, case, text
from app.models.models import Document, LLMAnalysis, ExtractedText, Entity, DesignElement, CommunicationFocus
from app.models.keyword_models import KeywordTaxonomy, DocumentKeyword, KeywordSynonym, SearchFeedback
from app.extensions import db
from app.services.preview_service import PreviewService
import time
from datetime import datetime
import logging

search_routes = Blueprint('search_routes', __name__)
preview_service = PreviewService()
logger = logging.getLogger(__name__)

# Track search response times for metrics
search_times = []
MAX_SEARCH_TIMES = 100

def record_search_time(response_time):
    """Record a search response time and maintain the list size"""
    global search_times
    search_times.append(response_time)
    if len(search_times) > MAX_SEARCH_TIMES:
        search_times = search_times[-MAX_SEARCH_TIMES:]

@search_routes.route('/enhanced-search')
def enhanced_search():
    """Enhanced search with hierarchical keyword support"""
    # Get search parameters
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 12, type=int)
    sort_by = request.args.get('sort_by', 'upload_date')
    sort_direction = request.args.get('sort_dir', 'desc')
    primary_category = request.args.get('primary_category', '')
    subcategory = request.args.get('subcategory', '')
    
    start_time = time.time()  # Start timing
    
    try:
        # Base document query
        base_query = Document.query.distinct()
        taxonomy_terms = []
        
        # Process search query if provided
        if query:
            # Find matching taxonomy terms
            taxonomy_terms = KeywordTaxonomy.find_matching_terms(query)
            logger.info(f"Found {len(taxonomy_terms)} taxonomy terms matching '{query}'")
            
            if taxonomy_terms:
                # Get IDs of all matching taxonomy terms
                taxonomy_ids = [term.id for term in taxonomy_terms]
                
                # Find documents with these taxonomy terms
                document_ids_with_keywords = db.session.query(DocumentKeyword.document_id).filter(
                    DocumentKeyword.taxonomy_id.in_(taxonomy_ids)
                ).distinct().subquery()
                
                base_query = base_query.filter(Document.id.in_(document_ids_with_keywords))
                logger.info(f"Filtered documents using taxonomy matches")
            else:
                # Fallback to traditional search if no taxonomy terms found
                logger.info(f"No taxonomy terms found, using traditional search")
                base_query = Document.query.outerjoin(Document.llm_analysis) \
                    .outerjoin(DocumentKeyword, Document.id == DocumentKeyword.document_id) \
                    .outerjoin(KeywordTaxonomy, DocumentKeyword.taxonomy_id == KeywordTaxonomy.id) \
                    .outerjoin(Document.entity) \
                    .outerjoin(Document.communication_focus) \
                    .outerjoin(Document.extracted_text) \
                    .filter(
                        or_(
                            Document.filename.ilike(f'%{query}%'),
                            LLMAnalysis.summary_description.ilike(f'%{query}%'),
                            KeywordTaxonomy.term.ilike(f'%{query}%'),
                            KeywordSynonym.synonym.ilike(f'%{query}%'),
                            Entity.client_name.ilike(f'%{query}%'),
                            Entity.opponent_name.ilike(f'%{query}%'),
                            CommunicationFocus.primary_issue.ilike(f'%{query}%'),
                            ExtractedText.main_message.ilike(f'%{query}%')
                        )
                    ).distinct()
        
        # Apply taxonomy filters if provided
        if primary_category:
            taxonomy_ids = db.session.query(KeywordTaxonomy.id).filter(
                KeywordTaxonomy.primary_category == primary_category
            )
            
            if subcategory:
                taxonomy_ids = taxonomy_ids.filter(KeywordTaxonomy.subcategory == subcategory)
                
            document_ids = db.session.query(DocumentKeyword.document_id).filter(
                DocumentKeyword.taxonomy_id.in_(taxonomy_ids)
            ).distinct().subquery()
            
            base_query = base_query.filter(Document.id.in_(document_ids))
        
        # Count results for pagination
        total_count = base_query.count()
        
        # Apply sorting
        if sort_by == 'filename':
            order_func = desc if sort_direction == 'desc' else asc
            base_query = base_query.order_by(order_func(Document.filename))
        else:
            # Default to sort by upload date
            order_func = desc if sort_direction == 'desc' else asc
            base_query = base_query.order_by(order_func(Document.upload_date))
        
        # Execute query with pagination
        paginated_result = base_query.paginate(page=page, per_page=per_page, error_out=False)
        documents = paginated_result.items
        
        # Format documents for display
        formatted_documents = format_documents_for_display(documents)
        
        # Create pagination information
        pagination = {
            'page': paginated_result.page,
            'per_page': per_page,
            'total': paginated_result.total,
            'pages': paginated_result.pages,
            'has_prev': paginated_result.has_prev,
            'has_next': paginated_result.has_next,
            'prev_page': paginated_result.prev_num if paginated_result.has_prev else None,
            'next_page': paginated_result.next_num if paginated_result.has_next else None
        }
        
        # Generate taxonomy facets for filtering
        taxonomy_facets = generate_taxonomy_facets(primary_category, subcategory)
        
        # Calculate response time
        response_time = (time.time() - start_time) * 1000  # in ms
        record_search_time(response_time)
        
        # Handle AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'results': formatted_documents,
                'pagination': pagination,
                'taxonomy_facets': taxonomy_facets,
                'matching_terms': [term.to_dict() for term in taxonomy_terms[:5]],  # Top 5 matches
                'response_time_ms': round(response_time, 2),
                'query': query
            })
        
        # Render HTML for browser requests
        return render_template(
            'pages/enhanced_search.html',
            documents=formatted_documents,
            pagination=pagination,
            taxonomy_facets=taxonomy_facets,
            matching_terms=taxonomy_terms[:5],
            query=query,
            sort_by=sort_by,
            sort_dir=sort_direction,
            primary_category=primary_category,
            subcategory=subcategory,
            response_time_ms=round(response_time, 2)
        )
        
    except Exception as e:
        logger.error(f"Enhanced search error: {str(e)}", exc_info=True)
        response_time = (time.time() - start_time) * 1000
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'error': str(e),
                'response_time_ms': round(response_time, 2)
            })
        
        return render_template(
            'pages/enhanced_search.html',
            documents=[],
            query=query,
            error=str(e)
        )

def format_documents_for_display(documents):
    """Format document data for display, including keyword information"""
    formatted_docs = []
    
    for doc in documents:
        # Get preview if possible
        preview = None
        try:
            preview = preview_service.get_preview(doc.filename)
        except Exception as e:
            logger.error(f"Preview generation failed for {doc.filename}: {str(e)}")
        
        # Build the document data
        document_data = {
            'id': doc.id,
            'filename': doc.filename,
            'upload_date': doc.upload_date.strftime('%Y-%m-%d %H:%M:%S'),
            'status': doc.status,
            'preview': preview,
            
            # Get analysis data if available
            'summary': doc.llm_analysis.summary_description if hasattr(doc, 'llm_analysis') and doc.llm_analysis else '',
            'document_type': doc.llm_analysis.campaign_type if hasattr(doc, 'llm_analysis') and doc.llm_analysis else '',
            'election_year': doc.llm_analysis.election_year if hasattr(doc, 'llm_analysis') and doc.llm_analysis else '',
            'document_tone': doc.llm_analysis.document_tone if hasattr(doc, 'llm_analysis') and doc.llm_analysis else '',
            
            # Entity data
            'client': doc.entity.client_name if hasattr(doc, 'entity') and doc.entity else '',
            'opponent': doc.entity.opponent_name if hasattr(doc, 'entity') and doc.entity else '',
            
            # Design elements
            'location': doc.design_elements.geographic_location if hasattr(doc, 'design_elements') and doc.design_elements else '',
            'target_audience': doc.design_elements.target_audience if hasattr(doc, 'design_elements') and doc.design_elements else '',
            
            # Communication focus
            'primary_issue': doc.communication_focus.primary_issue if hasattr(doc, 'communication_focus') and doc.communication_focus else '',
            
            # Extract text
            'main_message': doc.extracted_text.main_message if hasattr(doc, 'extracted_text') and doc.extracted_text else '',
            
            # Hierarchical keywords - new section
            'hierarchical_keywords': get_document_hierarchical_keywords(doc.id)
        }
        
        formatted_docs.append(document_data)
    
    return formatted_docs

def get_document_hierarchical_keywords(document_id):
    """Get all hierarchical keywords for a document"""
    try:
        # Query document keywords with taxonomy info
        keywords = db.session.query(
            DocumentKeyword, KeywordTaxonomy
        ).join(
            KeywordTaxonomy, DocumentKeyword.taxonomy_id == KeywordTaxonomy.id
        ).filter(
            DocumentKeyword.document_id == document_id
        ).all()
        
        # Format for display
        formatted_keywords = []
        for doc_kw, taxonomy in keywords:
            formatted_keywords.append({
                'id': taxonomy.id,
                'term': taxonomy.term,
                'primary_category': taxonomy.primary_category,
                'subcategory': taxonomy.subcategory,
                'relevance_score': doc_kw.relevance_score
            })
        
        return formatted_keywords
    except Exception as e:
        logger.error(f"Error fetching hierarchical keywords for doc {document_id}: {str(e)}")
        return []

def generate_taxonomy_facets(selected_primary=None, selected_subcategory=None):
    """Generate taxonomy facets for filtering"""
    try:
        # Get primary categories with counts
        primary_categories = db.session.query(
            KeywordTaxonomy.primary_category,
            func.count(KeywordTaxonomy.id.distinct()).label('count')
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
        logger.error(f"Error generating taxonomy facets: {str(e)}")
        return {'primary_categories': [], 'subcategories': []}

@search_routes.route('/api/search-feedback', methods=['POST'])
def submit_search_feedback():
    """API endpoint to submit search result feedback"""
    try:
        data = request.json
        
        # Validate required fields
        if not data.get('search_query') or not data.get('document_id') or not data.get('feedback_type'):
            return jsonify({
                'status': 'error',
                'message': 'Missing required fields'
            }), 400
        
        # Create feedback record
        feedback = SearchFeedback(
            search_query=data.get('search_query'),
            document_id=data.get('document_id'),
            feedback_type=data.get('feedback_type'),
            user_comment=data.get('comment', '')
        )
        
        db.session.add(feedback)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Feedback recorded successfully',
            'feedback_id': feedback.id
        })
    except Exception as e:
        logger.error(f"Error recording search feedback: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }), 500

@search_routes.route('/api/taxonomy/suggestions')
def taxonomy_suggestions():
    """API endpoint for taxonomy term suggestions/autocomplete"""
    try:
        query = request.args.get('q', '')
        if not query or len(query) < 2:
            return jsonify([])
        
        # Search for matching taxonomy terms
        terms = KeywordTaxonomy.query.filter(
            KeywordTaxonomy.term.ilike(f'%{query}%')
        ).limit(10).all()
        
        # Search for matching synonyms
        synonym_matches = db.session.query(
            KeywordTaxonomy
        ).join(
            KeywordSynonym, KeywordTaxonomy.id == KeywordSynonym.taxonomy_id
        ).filter(
            KeywordSynonym.synonym.ilike(f'%{query}%')
        ).limit(10).all()
        
        # Combine and deduplicate
        unique_terms = {term.id: term for term in terms + synonym_matches}
        
        # Format for autocomplete
        suggestions = []
        for term in unique_terms.values():
            suggestions.append({
                'id': term.id,
                'value': term.term,
                'label': f"{term.term} ({term.primary_category}: {term.subcategory})",
                'category': term.primary_category,
                'subcategory': term.subcategory
            })
        
        return jsonify(suggestions)
    except Exception as e:
        logger.error(f"Error getting taxonomy suggestions: {str(e)}")
        return jsonify([])

@search_routes.route('/api/taxonomy/related-terms/<int:term_id>')
def related_taxonomy_terms(term_id):
    """Get related taxonomy terms for a given term ID"""
    try:
        term = KeywordTaxonomy.query.get_or_404(term_id)
        related_terms = term.get_all_related_terms()
        
        # Format for response
        result = [term.to_dict() for term in related_terms]
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting related terms: {str(e)}")
        return jsonify([]), 500