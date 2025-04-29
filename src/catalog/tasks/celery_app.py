# src/catalog/tasks/celery_app.py
import os
import logging
from celery import Celery

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get queue names from constants
try:
    from src.catalog.constants import QUEUE_NAMES, DOCUMENT_STATUSES
except ImportError:
    # Fallback if constants not available yet
    DOCUMENT_STATUSES = {
        'PENDING': 'PENDING',
        'PROCESSING': 'PROCESSING',
        'COMPLETED': 'COMPLETED',
        'FAILED': 'FAILED'
    }

    QUEUE_NAMES = {
        'DOCUMENT_PROCESSING': 'document_processing',
        'ANALYSIS': 'analysis',
        'PREVIEWS': 'previews',
        'DEFAULT': 'celery'
    }

# Redis URLs
broker_url = os.environ.get('CELERY_BROKER_URL') or os.environ.get(
    'REDIS_URL') or 'redis://redis:6379/0'
result_backend = os.environ.get('CELERY_RESULT_BACKEND') or os.environ.get(
    'REDIS_URL') or 'redis://redis:6379/0'

# Log Redis configuration
safe_broker = broker_url.replace('redis://', 'redis://****:****@')
logger.info(f"Initializing Celery with broker: {safe_broker}")

# Initialize Celery
celery_app = Celery('src.catalog.tasks', broker=broker_url)

# Configure Celery
celery_app.conf.update(
    result_backend=result_backend,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

# Configure task routing
celery_app.conf.task_routes = {
    'src.catalog.tasks.document_tasks.process_document': {'queue': QUEUE_NAMES['DOCUMENT_PROCESSING']},
    'src.catalog.tasks.analyze_document': {'queue': QUEUE_NAMES['ANALYSIS']},
    'src.catalog.tasks.preview_tasks.generate_preview': {'queue': QUEUE_NAMES['PREVIEWS']},
    'src.catalog.tasks.dropbox_tasks.sync_dropbox': {'queue': QUEUE_NAMES['DOCUMENT_PROCESSING']},
    'src.catalog.tasks.embedding_tasks.generate_embeddings': {'queue': QUEUE_NAMES['DEFAULT']},
}

# Verify Redis connection on module import
try:
    with celery_app.connection_or_acquire() as conn:
        logger.info("Successfully connected to Redis")
except Exception as e:
    logger.error(f"Failed to connect to Redis: {str(e)}")
