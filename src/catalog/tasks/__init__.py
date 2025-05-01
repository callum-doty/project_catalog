# tasks/__init__.py

from .celery_app import celery_app
from .embedding_tasks import generate_embeddings
from .analysis_utils import check_minimum_analysis
# Import the tasks
try:
    from .document_tasks import process_document
except ImportError as e:
    print(f"Warning: Failed to import document_tasks: {str(e)}")
    process_document = None
    check_minimum_analysis = None

# Import recovery tasks
try:
    from .recovery_tasks import reprocess_document
except ImportError as e:
    print(f"Warning: Failed to import recovery_tasks: {str(e)}")
    reprocess_document = None

# Import preview tasks
try:
    from .preview_tasks import generate_preview
except ImportError as e:
    print(f"Warning: Failed to import preview_tasks: {str(e)}")
    generate_preview = None

# Update the __all__ list
__all__ = ['celery_app', 'test_task', 'check_minimum_analysis']
if process_document:
    __all__.append('process_document')
if reprocess_document:
    __all__.append('reprocess_document')
if generate_preview:
    __all__.append('generate_preview')
if generate_embeddings:
    __all__.append('generate_embeddings')
