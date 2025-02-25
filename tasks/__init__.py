# tasks/__init__.py
from .celery_app import celery_app
from .document_tasks import process_document
from .dropbox_tasks import sync_dropbox
from .recovery_tasks import reprocess_failed_documents, reprocess_specific_document

__all__ = [
    'celery_app',
    'process_document',
    'sync_dropbox',
    'reprocess_failed_documents',
    'reprocess_specific_document'
]