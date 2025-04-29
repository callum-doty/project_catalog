# app/utils/query_builders.py
"""
Reusable database query patterns for consistent and optimized database access
"""

from sqlalchemy import or_, func, desc, asc, case, text
from sqlalchemy.orm import joinedload
from src.catalog import db
from src.catalog.models import (
    Document, LLMAnalysis, ExtractedText, DesignElement,
    Classification, Entity, CommunicationFocus, LLMKeyword
)
from src.catalog.models import DocumentKeyword, KeywordTaxonomy, KeywordSynonym
from src.catalog.constants import DOCUMENT_STATUSES
from typing import List, Dict, Any, Optional, Union, Tuple


def build_document_base_query():
    """
    Create a base query for documents with commonly needed joins

    Returns:
        SQLAlchemy query object for Document
    """
    return Document.query


def build_document_with_relationships_query(
    include_llm_analysis=True,
    include_keywords=True,
    include_extracted_text=True,
    include_design_elements=True,
    include_entity=True,
    include_communication_focus=True
):
    """
    Build a query for documents with configurable eager loading of relationships

    Args:
        include_llm_analysis: Whether to include LLM analysis
        include_keywords: Whether to include keywords (requires include_llm_analysis=True)
        include_extracted_text: Whether to include extracted text
        include_design_elements: Whether to include design elements
        include_entity: Whether to include entity information
        include_communication_focus: Whether to include communication focus

    Returns:
        SQLAlchemy query object with specified eager loading options
    """
    query = Document.query

    # Add eager loading options
    if include_llm_analysis:
        if include_keywords:
            query = query.options(
                joinedload(Document.llm_analysis).joinedload(
                    LLMAnalysis.keywords)
            )
        else:
            query = query.options(joinedload(Document.llm_analysis))

    if include_extracted_text:
        query = query.options(joinedload(Document.extracted_text))

    if include_design_elements:
        query = query.options(joinedload(Document.design_elements))

    if include_entity:
        query = query.options(joinedload(Document.entity))

    if include_communication_focus:
        query = query.options(joinedload(Document.communication_focus))

    return query


def filter_by_status(query, status=None):
    """
    Filter documents by status

    Args:
        query: Base SQLAlchemy query
        status: Status to filter by (use None for all)

    Returns:
        Filtered SQLAlchemy query
    """
    if status:
        if isinstance(status, list):
            return query.filter(Document.status.in_(status))
        else:
            return query.filter(Document.status == status)
    return query


def filter_by_document_type(query, document_type=None):
    """
    Filter documents by document type (campaign_type in LLMAnalysis)

    Args:
        query: Base SQLAlchemy query
        document_type: Document type to filter by (use None for all)

    Returns:
        Filtered SQLAlchemy query
    """
    if not document_type:
        return query

    # Need to join with LLMAnalysis if not already joined
    if not query._joinpoint.left.description.name == 'llm_analysis':
        query = query.join(LLMAnalysis, Document.id ==
                           LLMAnalysis.document_id, isouter=True)

    if isinstance(document_type, list) or isinstance(document_type, tuple):
        return query.filter(LLMAnalysis.campaign_type.in_(document_type))
    else:
        return query.filter(LLMAnalysis.campaign_type == document_type)


def filter_by_year(query, year=None):
    """
    Filter documents by election year

    Args:
        query: Base SQLAlchemy query
        year: Year to filter by (use None for all)

    Returns:
        Filtered SQLAlchemy query
    """
    if not year:
        return query

    # Need to join with LLMAnalysis if not already joined
    if not query._joinpoint.left.description.name == 'llm_analysis':
        query = query.join(LLMAnalysis, Document.id ==
                           LLMAnalysis.document_id, isouter=True)

    return query.filter(LLMAnalysis.election_year == year)


def filter_by_location(query, location=None):
    """
    Filter documents by geographic location

    Args:
        query: Base SQLAlchemy query
        location: Location to filter by (use None for all)

    Returns:
        Filtered SQLAlchemy query
    """
    if not location:
        return query

    # Join with DesignElement
    query = query.join(
        DesignElement, Document.id == DesignElement.document_id, isouter=True
    ).filter(
        func.lower(DesignElement.geographic_location).like(
            f"%{location.lower()}%")
    )

    return query


def filter_by_taxonomy(query, primary_category=None, subcategory=None, specific_term=None):
    """
    Filter documents by taxonomy terms

    Args:
        query: Base SQLAlchemy query
        primary_category: Primary category to filter by
        subcategory: Subcategory to filter by (requires primary_category)
        specific_term: Specific term to filter by (requires primary_category and subcategory)

    Returns:
        Filtered SQLAlchemy query
    """
    if not primary_category:
        return query

    taxonomy_query = db.session.query(DocumentKeyword.document_id).join(
        KeywordTaxonomy, DocumentKeyword.taxonomy_id == KeywordTaxonomy.id
    ).filter(
        KeywordTaxonomy.primary_category == primary_category
    )

    if subcategory:
        taxonomy_query = taxonomy_query.filter(
            KeywordTaxonomy.subcategory == subcategory)

    if specific_term:
        taxonomy_query = taxonomy_query.filter(
            KeywordTaxonomy.term == specific_term)

    taxonomy_ids = taxonomy_query.subquery()
    query = query.join(taxonomy_ids, Document.id == taxonomy_ids.c.document_id)

    return query


def apply_sorting(query, sort_by='upload_date', sort_direction='desc'):
    """
    Apply sorting to document query

    Args:
        query: Base SQLAlchemy query
        sort_by: Field to sort by
        sort_direction: Direction to sort (asc/desc)

    Returns:
        Sorted SQLAlchemy query
    """
    if sort_by == 'filename':
        if sort_direction.lower() == 'desc':
            return query.order_by(Document.filename.desc())
        else:
            return query.order_by(Document.filename.asc())
    elif sort_by == 'status':
        if sort_direction.lower() == 'desc':
            return query.order_by(Document.status.desc())
        else:
            return query.order_by(Document.status.asc())
    else:  # Default to upload_date
        if sort_direction.lower() == 'desc':
            return query.order_by(Document.upload_date.desc())
        else:
            return query.order_by(Document.upload_date.asc())


def apply_pagination(query, page=1, per_page=12):
    """
    Apply pagination to query

    Args:
        query: Base SQLAlchemy query
        page: Page number (1-indexed)
        per_page: Items per page

    Returns:
        Tuple of (paginated query, pagination data dict)
    """
    # Get total count before pagination
    total_count = query.count()

    # Apply pagination
    paginated_query = query.offset((page - 1) * per_page).limit(per_page)

    # Calculate pagination info
    pages = (total_count + per_page - 1) // per_page if per_page > 0 else 0

    pagination_data = {
        'page': page,
        'per_page': per_page,
        'total': total_count,
        'pages': pages,
        'has_prev': page > 1,
        'has_next': page < pages,
        'prev_page': page - 1 if page > 1 else None,
        'next_page': page + 1 if page < pages else None
    }

    return paginated_query, pagination_data


def get_failed_documents_query():
    """
    Get query for documents with FAILED status

    Returns:
        SQLAlchemy query for failed documents
    """
    return Document.query.filter_by(status=DOCUMENT_STATUSES['FAILED']).order_by(Document.upload_date.desc())


def get_stuck_documents_query(hours=1):
    """
    Get query for documents stuck in PENDING or PROCESSING state

    Args:
        hours: Minimum hours since upload to consider a document stuck

    Returns:
        SQLAlchemy query for stuck documents
    """
    from datetime import datetime, timedelta

    time_threshold = datetime.utcnow() - timedelta(hours=hours)

    return Document.query.filter(
        Document.status.in_([DOCUMENT_STATUSES['PENDING'],
                            DOCUMENT_STATUSES['PROCESSING']]),
        Document.upload_date < time_threshold
    ).order_by(Document.upload_date.desc())


def search_document_ids_by_vector(embeddings, similarity_threshold=0.7):
    """
    Search for document IDs using vector similarity (if available)

    Args:
        embeddings: Vector embeddings to search with
        similarity_threshold: Minimum similarity threshold

    Returns:
        SQLAlchemy query with document IDs
    """
    try:
        # Check if vector search is available
        if not hasattr(Document, 'embeddings'):
            return None

        # Use cosine similarity with pgvector
        doc_matches = db.session.query(
            Document.id,
            (1 - (Document.embeddings.op('<=>')(embeddings))).label('similarity')
        ).filter(
            Document.embeddings.is_not(None)
        ).filter(
            (1 - (Document.embeddings.op('<=>')(embeddings))) > similarity_threshold
        ).subquery()

        # Find analysis content with similar embeddings
        analysis_matches = db.session.query(
            LLMAnalysis.document_id,
            (1 - (LLMAnalysis.embeddings.op('<=>')(embeddings))).label('similarity')
        ).filter(
            LLMAnalysis.embeddings.is_not(None)
        ).filter(
            (1 - (LLMAnalysis.embeddings.op('<=>')(embeddings))) > similarity_threshold
        ).subquery()

        # Combine the results and order by similarity score
        combined_query = db.session.query(
            Document.id
        ).outerjoin(
            doc_matches, Document.id == doc_matches.c.id
        ).outerjoin(
            analysis_matches, Document.id == analysis_matches.c.document_id
        ).filter(
            or_(
                doc_matches.c.id.is_not(None),
                analysis_matches.c.document_id.is_not(None)
            )
        ).order_by(
            (func.coalesce(doc_matches.c.similarity, 0) +
                func.coalesce(analysis_matches.c.similarity, 0)).desc()
        )

        return combined_query
    except Exception:
        # Return None if vector search fails
        return None


def get_document_statistics(days=30):
    """
    Get statistics about documents

    Args:
        days: Number of days to look back

    Returns:
        Dictionary with document statistics
    """
    from datetime import datetime, timedelta
    time_period = datetime.utcnow() - timedelta(days=days)

    # Base query for recent documents
    base_query = Document.query.filter(Document.upload_date >= time_period)
    total_docs = base_query.count()

    # Calculate counts by status
    completed = base_query.filter(
        Document.status == DOCUMENT_STATUSES['COMPLETED']).count()
    failed = base_query.filter(
        Document.status == DOCUMENT_STATUSES['FAILED']).count()
    pending = base_query.filter(
        Document.status == DOCUMENT_STATUSES['PENDING']).count()
    processing = base_query.filter(
        Document.status == DOCUMENT_STATUSES['PROCESSING']).count()

    # Calculate success rate
    success_rate = (completed / total_docs * 100) if total_docs > 0 else 0

    # Daily document processing volume
    daily_processing = db.session.query(
        func.date(Document.upload_date).label('date'),
        func.count().label('total'),
        func.sum(case((Document.status == DOCUMENT_STATUSES['COMPLETED'], 1), else_=0)).label(
            'completed'),
        func.sum(case((Document.status == DOCUMENT_STATUSES['FAILED'], 1), else_=0)).label(
            'failed')
    ).filter(
        Document.upload_date >= time_period
    ).group_by(
        text('date')
    ).order_by(
        text('date')
    ).all()

    # Format daily processing data
    daily_data = [
        {
            'date': date.strftime('%Y-%m-%d'),
            'total': total,
            'completed': completed,
            'failed': failed,
            'success_rate': (completed / total * 100) if total > 0 else 0
        }
        for date, total, completed, failed in daily_processing
    ]

    return {
        'document_counts': {
            'total': total_docs,
            'completed': completed,
            'failed': failed,
            'pending': pending,
            'processing': processing
        },
        'processing_success_rate': success_rate,
        'daily_processing': daily_data
    }
