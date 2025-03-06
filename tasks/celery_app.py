# tasks/celery_app.py

from celery import Celery
from celery.utils.log import get_task_logger
from celery.schedules import crontab
import os

# Initialize Celery
celery_app = Celery('tasks', broker='redis://redis:6379/0')

redis_url = os.environ.get('REDIS_URL')
if redis_url:
    # Print the URL (without credentials for security)
    url_parts = redis_url.split('@')
    if len(url_parts) > 1:
        safe_url = 'redis://***:***@' + url_parts[1]
    else:
        safe_url = 'redis://***:***@[hidden]'
    print(f"Using Redis URL: {safe_url}")
    
    # Explicitly set Celery environment variables
    os.environ['CELERY_BROKER_URL'] = redis_url
    os.environ['CELERY_RESULT_BACKEND'] = redis_url
else:
    print("WARNING: No Redis URL found in environment!")

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
        'tasks.reprocess_failed_documents': {'queue': 'celery'}, 
        'tasks.reprocess_specific_document': {'queue': 'celery'}  
    },
    broker_connection_retry_on_startup=True
)

celery_app.conf.beat_schedule = {
    'sync-dropbox-every-5-minutes': {
        'task': 'tasks.dropbox_tasks.sync_dropbox',
        'schedule': crontab(minute='*/5'),  # Run every 5 minutes
    },
}

logger = get_task_logger(__name__)