# app/routes/search_routes.py

from flask import Blueprint, render_template, request, jsonify, current_app, flash
from sqlalchemy import or_, func, desc, asc, case, text
import logging
from flask import Blueprint, render_template, request, session, flash, redirect, url_for, jsonify, current_app
from werkzeug.utils import secure_filename
import os
import app
from sqlalchemy.orm import joinedload
from datetime import datetime
from app.services.storage_service import MinIOStorage
from app.extensions import db
from app.models.models import Document, LLMAnalysis, LLMKeyword, Classification, DesignElement, ExtractedText, DropboxSync, Entity, CommunicationFocus
from app.models.keyword_models import KeywordTaxonomy, KeywordSynonym, DocumentKeyword, SearchFeedback
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
from app.services.preview_service import PreviewService


search_routes = Blueprint('search_routes', __name__)
preview_service = PreviewService()
logger = logging.getLogger(__name__)

# Track search response times for metrics
search_times = []
MAX_SEARCH_TIMES = 100


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
        logger.error(f"Error getting hierarchical keywords: {str(e)}")
        return []





def record_search_time(response_time):
    """Record a search response time and maintain the list size"""
    global search_times
    search_times.append(response_time)
    if len(search_times) > MAX_SEARCH_TIMES:
        search_times = search_times[-MAX_SEARCH_TIMES:]


@search_routes.route('/')
@monitor_query
@cache.cached(timeout=60, query_string=True)
def search_documents():
    """Search implementation with full-text search capability"""
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

    start_time = time.time()
    taxonomy_facets = {'primary_categories': [], 'subcategories': []}
    taxonomy_terms = []
    formatted_documents = []

    try:
        base_query = db.session.query(Document.id)

        if query:
            if hasattr(Document, 'search_vector') and document_has_column(Document, 'search_vector'):
                tsquery = func.plainto_tsquery('english', query)
                doc_matches = db.session.query(Document.id).filter(
                    Document.search_vector.op('@@')(tsquery)
                ).subquery()
                llm_matches = db.session.query(LLMAnalysis.document_id).filter(
                    LLMAnalysis.search_vector.op('@@')(tsquery)
                ).subquery()
                text_matches = db.session.query(ExtractedText.document_id).filter(
                    ExtractedText.search_vector.op('@@')(tsquery)
                ).subquery()

                combined_matches = base_query.join(
                    doc_matches, Document.id == doc_matches.c.id, isouter=True
                ).union(
                    db.session.query(Document.id).join(
                        llm_matches, Document.id == llm_matches.c.document_id, isouter=True
                    ),
                    db.session.query(Document.id).join(
                        text_matches, Document.id == text_matches.c.document_id, isouter=True
                    )
                ).subquery()

                base_query = db.session.query(Document.id).join(
                    combined_matches, Document.id == combined_matches.c.id
                )
            else:
                base_query = base_query.outerjoin(
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
                        ExtractedText.main_message.ilike(f'%{query}%'),
                        ExtractedText.supporting_text.ilike(f'%{query}%')
                    )
                )

        if filter_type:
            base_query = base_query.join(LLMAnalysis, Document.id == LLMAnalysis.document_id, isouter=True)
            if ',' in filter_type:
                doc_type_list = filter_type.split(',')
                base_query = base_query.filter(LLMAnalysis.document_tone.in_(doc_type_list))
            else:
                base_query = base_query.filter(LLMAnalysis.document_tone == filter_type)

        if filter_year:
            if not filter_type:
                base_query = base_query.join(LLMAnalysis, Document.id == LLMAnalysis.document_id, isouter=True)
            base_query = base_query.filter(LLMAnalysis.election_year == filter_year)

        if filter_location:
            base_query = base_query.join(
                DesignElement, Document.id == DesignElement.document_id, isouter=True
            ).filter(
                func.lower(DesignElement.geographic_location).like(f"%{filter_location.lower()}%")
            )

        if primary_category:
            taxonomy_query = db.session.query(DocumentKeyword.document_id).join(
                KeywordTaxonomy, DocumentKeyword.taxonomy_id == KeywordTaxonomy.id
            ).filter(
                KeywordTaxonomy.primary_category == primary_category
            )
            if subcategory:
                taxonomy_query = taxonomy_query.filter(KeywordTaxonomy.subcategory == subcategory)

            taxonomy_ids = taxonomy_query.subquery()
            base_query = base_query.join(taxonomy_ids, Document.id == taxonomy_ids.c.document_id)

        base_query = base_query.distinct()
        total_count = base_query.count()

        if sort_by == 'filename':
            document_query = db.session.query(Document).filter(Document.id.in_(base_query))
            document_query = document_query.order_by(
                Document.filename.desc() if sort_direction == 'desc' else Document.filename.asc()
            )
        else:
            document_query = db.session.query(Document).filter(Document.id.in_(base_query))
            document_query = document_query.order_by(
                Document.upload_date.desc() if sort_direction == 'desc' else Document.upload_date.asc()
            )

        documents = document_query.offset((page - 1) * per_page).limit(per_page).all()
        document_ids = [doc.id for doc in documents]

        if document_ids:
            documents = Document.query.filter(Document.id.in_(document_ids)).options(
                joinedload(Document.llm_analysis).joinedload(LLMAnalysis.keywords),
                joinedload(Document.entity),
                joinedload(Document.design_elements),
                joinedload(Document.communication_focus),
                joinedload(Document.extracted_text)
            ).all()
            id_to_doc = {doc.id: doc for doc in documents}
            documents = [id_to_doc[doc_id] for doc_id in document_ids if doc_id in id_to_doc]
        else:
            documents = []

        all_keywords = get_document_hierarchical_keywords_bulk(document_ids) if document_ids else {}

        if documents:
            missing_previews = []
            for filename in [doc.filename for doc in documents]:
                cache_key = f"preview:{filename}"
                if not cache.get(cache_key):
                    missing_previews.append(filename)
            if missing_previews:
                try:
                    from tasks.preview_tasks import generate_preview
                    for filename in missing_previews:
                        generate_preview.delay(filename)
                except Exception as e:
                    current_app.logger.error(f"Error queueing preview generation: {str(e)}")

        pagination = {
            'page': page,
            'per_page': per_page,
            'total': total_count,
            'pages': (total_count + per_page - 1) // per_page,
            'has_prev': page > 1,
            'has_next': page < ((total_count + per_page - 1) // per_page),
            'prev_page': page - 1 if page > 1 else None,
            'next_page': page + 1 if page < ((total_count + per_page - 1) // per_page) else None
        }

        results = []
        for doc in documents:
            try:
                preview = preview_service.get_preview(doc.filename)
            except Exception as e:
                current_app.logger.error(f"Preview generation failed for {doc.filename}: {str(e)}")
                preview = None

            formatted_doc = {
                'id': doc.id,
                'filename': doc.filename,
                'upload_date': doc.upload_date.strftime('%Y-%m-%d %H:%M:%S'),
                'status': doc.status,
                'preview': preview,
                'summary': doc.llm_analysis.summary_description if doc.llm_analysis else '',
                'keywords': [
                    {
                        'text': kw.keyword,
                        'category': kw.category
                    } for kw in (doc.llm_analysis.keywords if doc.llm_analysis else [])
                    if hasattr(kw, 'keyword')
                ],
                'document_type': doc.llm_analysis.campaign_type if doc.llm_analysis else '',
                'election_year': doc.llm_analysis.election_year if doc.llm_analysis else '',
                'document_tone': doc.llm_analysis.document_tone if doc.llm_analysis else '',
                'client': doc.entity.client_name if doc.entity else '',
                'opponent': doc.entity.opponent_name if doc.entity else '',
                'location': doc.design_elements.geographic_location if doc.design_elements else '',
                'target_audience': doc.design_elements.target_audience if doc.design_elements else '',
                'primary_issue': doc.communication_focus.primary_issue if doc.communication_focus else '',
                'main_message': doc.extracted_text.main_message if doc.extracted_text else '',
                'hierarchical_keywords': all_keywords.get(doc.id, [])
            }
            results.append(formatted_doc)

        taxonomy_facets = generate_taxonomy_facets(primary_category, subcategory)
        response_time = (time.time() - start_time) * 1000
        record_search_time(response_time)

        # Check for AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'results': results,
                'pagination': pagination,
                'taxonomy_facets': taxonomy_facets,
                'matching_terms': [term.to_dict() for term in taxonomy_terms[:5]] if taxonomy_terms else [],
                'response_time_ms': round(response_time, 2),
                'query': query
            })
        
        # Render HTML for browser requests
        return render_template(
            'pages/search.html', 
            documents=results,
            pagination=pagination,
            taxonomy_facets=taxonomy_facets,
            matching_terms=taxonomy_terms[:5] if taxonomy_terms else [],
            query=query,
            sort_by=sort_by,
            sort_dir=sort_direction,
            primary_category=primary_category,
            subcategory=subcategory,
            filter_type=filter_type,
            filter_year=filter_year,
            filter_location=filter_location,
            response_time_ms=round(response_time, 2)
        )
    
    

    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        record_search_time(response_time)
        current_app.logger.error(f"Search error: {str(e)}", exc_info=True)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'error': str(e),
                'results': [],
                'pagination': None,
                'response_time_ms': round(response_time, 2)
            })

        return render_template(
            'pages/search.html',
            documents=[],
            query=query,
            error=str(e),
            taxonomy_facets=taxonomy_facets
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

def get_document_hierarchical_keywords_bulk(document_ids):
    """Efficiently get hierarchical keywords for multiple documents at once"""
    try:
        from app.models.keyword_models import DocumentKeyword, KeywordTaxonomy
        
        # Single query to get all keywords for all documents
        keywords_data = db.session.query(
            DocumentKeyword, KeywordTaxonomy
        ).join(
            KeywordTaxonomy, DocumentKeyword.taxonomy_id == KeywordTaxonomy.id
        ).filter(
            DocumentKeyword.document_id.in_(document_ids)
        ).all()
        
        # Organize by document ID
        results = {doc_id: [] for doc_id in document_ids}
        
        for doc_kw, taxonomy in keywords_data:
            results[doc_kw.document_id].append({
                'id': taxonomy.id,
                'term': taxonomy.term,
                'primary_category': taxonomy.primary_category,
                'subcategory': taxonomy.subcategory,
                'relevance_score': doc_kw.relevance_score
            })
        
        return results
    except Exception as e:
        current_app.logger.error(f"Error getting hierarchical keywords: {str(e)}")
        return {doc_id: [] for doc_id in document_ids}

def generate_taxonomy_facets(selected_primary=None, selected_subcategory=None):
    """Generate taxonomy facets with more efficient queries"""
    try:
        from app.models.keyword_models import KeywordTaxonomy, DocumentKeyword
        
        # Use count queries with joins optimized by added indexes
        
        # For primary categories, add a CTE for used taxonomies
        used_taxonomies = db.session.query(
            DocumentKeyword.taxonomy_id
        ).distinct().subquery()
        
        # Get primary categories with counts, only for taxonomies actually in use
        primary_categories = db.session.query(
            KeywordTaxonomy.primary_category,
            func.count(KeywordTaxonomy.id.distinct()).label('count')
        ).join(
            used_taxonomies, KeywordTaxonomy.id == used_taxonomies.c.taxonomy_id
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
                used_taxonomies, KeywordTaxonomy.id == used_taxonomies.c.taxonomy_id
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


def record_search_time(response_time):
    """Record a search response time and maintain the list size"""
    global search_times
    search_times.append(response_time)
    if len(search_times) > MAX_SEARCH_TIMES:
        search_times = search_times[-MAX_SEARCH_TIMES:]