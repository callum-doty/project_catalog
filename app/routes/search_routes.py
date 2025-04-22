# app/routes/search_routes.py (refactored)

from flask import Blueprint, render_template, request, jsonify, current_app
from app.services.search_service import SearchService
from app.extensions import cache
from app.constants import CACHE_TIMEOUTS
from app.utils import monitor_query
from app.models import Document
import time

search_routes = Blueprint('search_routes', __name__)
search_service = SearchService()


from app.utils.query_builders import (
    build_document_with_relationships_query,
    filter_by_document_type,
    filter_by_year,
    filter_by_location,
    filter_by_taxonomy,
    apply_sorting,
    apply_pagination
)


@search_routes.route('/')
@monitor_query
@cache.cached(timeout=CACHE_TIMEOUTS['SEARCH'], query_string=True)
def search_documents():
    """Search documents with multiple strategies and filters"""
    start_time = time.time()
    
    try:
        # Extract all parameters from the request
        query = request.args.get('q', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 12, type=int)
        sort_by = request.args.get('sort_by', 'upload_date')
        sort_direction = request.args.get('sort_dir', 'desc')
        filter_type = request.args.get('filter_type', '')
        filter_year = request.args.get('filter_year', '')
        filter_location = request.args.get('filter_location', '')
        primary_category = request.args.get('primary_category', '')
        subcategory = request.args.get('subcategory', '')
        specific_term = request.args.get('specific_term', '')
        
        # Default values
        expanded_query = None
        taxonomy_facets = {'primary_categories': [], 'subcategories': [], 'terms': []}
        
        # Step 1: Get document IDs matching the search query
        document_ids = []
        
        if query:
            # Use the search service to get document IDs
            # This part stays in the search service since it's specific to search
            expanded_query = search_service.expand_query(query)
            
            if isinstance(expanded_query, set):
                expanded_query_list = list(expanded_query)
            else:
                expanded_query_list = [expanded_query]
                
            # Based on search strategy, get matching document IDs
            document_ids = search_service.search_document_ids(query, expanded_query)
        
        # Step 2: Build base query for documents with relationships
        if query and document_ids:
            # Filter by document IDs from search results
            base_query = build_document_with_relationships_query().filter(
                Document.id.in_(document_ids)
            )
        else:
            # No search query, get all documents
            base_query = build_document_with_relationships_query()
        
        # Step 3: Apply filters
        if filter_type:
            base_query = filter_by_document_type(base_query, filter_type)
            
        if filter_year:
            base_query = filter_by_year(base_query, filter_year)
            
        if filter_location:
            base_query = filter_by_location(base_query, filter_location)
        
        if primary_category:
            base_query = filter_by_taxonomy(
                base_query,
                primary_category=primary_category,
                subcategory=subcategory,
                specific_term=specific_term
            )
        
        # Step 4: Apply sorting and pagination
        sorted_query = apply_sorting(base_query, sort_by, sort_direction)
        
        # Get total count and apply pagination
        paginated_query, pagination = apply_pagination(sorted_query, page, per_page)
        
        # Step 5: Get documents
        documents = paginated_query.all()
        
        # Step 6: Format documents for display
        document_ids = [doc.id for doc in documents]
        
        if document_ids:
            # Get hierarchical keywords for all documents
            all_keywords = search_service.get_document_hierarchical_keywords_bulk(document_ids)
            
            # Format documents for display
            formatted_documents = search_service._format_documents_for_display(documents, all_keywords)
            
            # Queue missing previews for generation
            search_service._queue_missing_previews([doc.filename for doc in documents])
        else:
            formatted_documents = []
        
        # Step 7: Generate taxonomy facets for filtering
        taxonomy_facets = search_service.generate_taxonomy_facets(primary_category, subcategory, specific_term)
        
        # Calculate response time
        response_time = (time.time() - start_time) * 1000
        
        # Check for AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Return JSON for AJAX requests
            return jsonify({
                'results': formatted_documents,
                'pagination': pagination,
                'taxonomy_facets': taxonomy_facets,
                'expanded_terms': expanded_query_list if isinstance(expanded_query, set) else expanded_query,
                'response_time_ms': round(response_time, 2),
                'query': query
            })
        else:
            # Return HTML for browser requests
            return render_template(
                'pages/search.html', 
                documents=formatted_documents,
                pagination=pagination,
                taxonomy_facets=taxonomy_facets,
                expanded_terms=expanded_query_list if isinstance(expanded_query, set) else [],
                query=query,
                sort_by=sort_by,
                sort_dir=sort_direction,
                primary_category=primary_category,
                subcategory=subcategory,
                specific_term=specific_term,
                filter_type=filter_type,
                filter_year=filter_year,
                filter_location=filter_location,
                response_time_ms=round(response_time, 2)
            )
            
    except Exception as e:
        current_app.logger.error(f"Search error: {str(e)}", exc_info=True)
        
        response_time = (time.time() - start_time) * 1000
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'error': str(e),
                'results': [],
                'pagination': None,
                'expanded_terms': [],
                'response_time_ms': round(response_time, 2)
            })
        else:
            return render_template(
                'pages/search.html',
                documents=[],
                query=query,
                error=str(e),
                taxonomy_facets={'primary_categories': [], 'subcategories': [], 'terms': []},
                expanded_terms=[],
                response_time_ms=round(response_time, 2)
            )

@search_routes.route('/api/taxonomy/suggestions')
def taxonomy_suggestions():
    """API endpoint for taxonomy term suggestions/autocomplete"""
    try:
        query = request.args.get('q', '')
        if not query or len(query) < 2:
            return jsonify([])
        
        # Use search service to get taxonomy suggestions
        suggestions = search_service.get_taxonomy_suggestions(query)
        return jsonify(suggestions)
    except Exception as e:
        current_app.logger.error(f"Error getting taxonomy suggestions: {str(e)}")
        return jsonify([])

@search_routes.route('/api/taxonomy/related-terms/<int:term_id>')
def related_taxonomy_terms(term_id):
    """Get related taxonomy terms for a given term ID"""
    try:
        # Use search service to get related terms
        related_terms = search_service.get_related_taxonomy_terms(term_id)
        return jsonify(related_terms)
    except Exception as e:
        current_app.logger.error(f"Error getting related terms: {str(e)}")
        return jsonify([]), 500

@search_routes.route('/api/search-feedback', methods=['POST'])
def submit_search_feedback():
    """API endpoint to submit search result feedback"""
    try:
        # Use search service to handle feedback
        feedback_result = search_service.record_search_feedback(request.json)
        return jsonify(feedback_result)
    except Exception as e:
        current_app.logger.error(f"Error recording search feedback: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }), 500