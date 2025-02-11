# tasks/celery_app.py

import os
from celery import Celery
from celery.utils.log import get_task_logger
from celery.schedules import crontab

logger = get_task_logger(__name__)

BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')
RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')

celery_app = Celery('tasks', broker=BROKER_URL, backend=RESULT_BACKEND)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    broker_connection_retry_on_startup=True,
)

# Task routes configuration
celery_app.conf.task_routes = {
    'tasks.process_document': {'queue': 'document_processing'},
    'tasks.sync_dropbox': {'queue': 'document_processing'},
}

# Beat schedule for Dropbox sync
celery_app.conf.beat_schedule = {
    'sync-dropbox-every-5-minutes': {
        'task': 'tasks.sync_dropbox',
        'schedule': crontab(minute='*/5'),
    },
}