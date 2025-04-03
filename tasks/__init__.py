# tasks/__init__.py

from .celery_app import celery_app
from .test import test_task

# Import the tasks
try:
    from .document_tasks import process_document
except ImportError as e:
    print(f"Warning: Failed to import document_tasks: {str(e)}")
    process_document = None
    
# Import recovery tasks
try:
    from .recovery_tasks import reprocess_document
except ImportError as e:
    print(f"Warning: Failed to import recovery_tasks: {str(e)}")
    reprocess_document = None

# Update the __all__ list
__all__ = ['celery_app', 'test_task']
if process_document:
    __all__.append('process_document')
if reprocess_document:
    __all__.append('reprocess_document')