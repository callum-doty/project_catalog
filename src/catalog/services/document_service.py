

from src.catalog.models import Document
from src.catalog import cache, db


@cache.memoize(timeout=60)
def get_document_count(status=None):
    """Get document count with optional status filtering"""
    query = Document.query
    if status:
        query = query.filter(Document.status == status)
    return query.count()


@cache.memoize(timeout=60)
def get_document_counts_by_status():
    """Get document counts grouped by status"""
    counts = {
        'total': get_document_count(),
        'completed': get_document_count('COMPLETED'),
        'failed': get_document_count('FAILED'),
        'pending': get_document_count('PENDING'),
        'processing': get_document_count('PROCESSING')
    }
    return counts
