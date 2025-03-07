# tasks/__init__.py

# Import Redis fix before anything else
try:
    import fix_redis
    print("Redis configuration applied successfully")
except ImportError:
    print("Warning: fix_redis.py not found")

from .celery_app import celery_app
from .utils import TASK_STATUSES, handle_task_failure, logger

# Import task modules
try:
    from .document_tasks import process_document
except ImportError as e:
    print(f"Warning: Failed to import document_tasks: {str(e)}")
    process_document = None

try:
    from .dropbox_tasks import sync_dropbox
except ImportError as e:
    print(f"Warning: Failed to import dropbox_tasks: {str(e)}")
    sync_dropbox = None

__all__ = [
    'celery_app',
    'TASK_STATUSES',
    'handle_task_failure',
    'logger'
]

if process_document:
    __all__.append('process_document')

if sync_dropbox:
    __all__.append('sync_dropbox')