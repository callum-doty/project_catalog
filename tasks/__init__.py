# tasks/__init__.py
from .celery_app import celery_app
from .test import test_task  # Keep this for testing

# Only import these after the basic celery setup is working
try:
    from .document_tasks import process_document
except ImportError as e:
    print(f"Warning: Failed to import document_tasks: {str(e)}")
    process_document = None

__all__ = ['celery_app', 'test_task']
if process_document:
    __all__.append('process_document')