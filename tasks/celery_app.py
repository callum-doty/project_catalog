# tasks/celery_app.py

from celery import Celery
from celery.utils.log import get_task_logger

# Initialize Celery
celery_app = Celery('tasks', broker='redis://redis:6379/0')

# Configure Celery
celery_app.conf.update(
    result_backend='redis://redis:6379/0',
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    imports=[
        'tasks.document_tasks',
        'tasks.dropbox_tasks'
    ],
    task_routes={
        'tasks.document_tasks.process_document': {'queue': 'document_processing'},
        'tasks.dropbox_tasks.sync_dropbox': {'queue': 'document_processing'},
    },
    broker_connection_retry_on_startup=True
)

logger = get_task_logger(__name__)