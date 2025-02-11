# tasks/__init__.py

from .celery_app import celery_app
from .utils import TASK_STATUSES, handle_task_failure, logger
from .document_tasks import process_document
from .dropbox_tasks import sync_dropbox

__all__ = [
    'celery_app',
    'process_document',
    'sync_dropbox',
    'TASK_STATUSES',
    'handle_task_failure',
    'logger'
]