# src/catalog/tasks/celery_app.py
import os
import logging
from celery import Celery

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get queue names from constants (moved before Celery app initialization)
try:
    from src.catalog.constants import QUEUE_NAMES, DOCUMENT_STATUSES
except ImportError:
    # Fallback if constants not available yet
    DOCUMENT_STATUSES = {
        "PENDING": "PENDING",
        "PROCESSING": "PROCESSING",
        "COMPLETED": "COMPLETED",
        "FAILED": "FAILED",
    }

    QUEUE_NAMES = {
        "DOCUMENT_PROCESSING": "document_processing",
        "ANALYSIS": "analysis",
        "PREVIEWS": "previews",
        "DEFAULT": "celery",
    }

# Redis URLs
broker_url = (
    os.environ.get("CELERY_BROKER_URL")
    or os.environ.get("REDIS_URL")
    or "redis://redis:6379/0"
)
result_backend = (
    os.environ.get("CELERY_RESULT_BACKEND")
    or os.environ.get("REDIS_URL")
    or "redis://redis:6379/0"
)

# Log Redis configuration
safe_broker = broker_url.replace("redis://", "redis://****:****@")
logger.info(f"Initializing Celery with broker: {safe_broker}")

# Initialize Celery ONCE
celery_app = Celery("src.catalog.tasks", broker=broker_url)

# Autodiscover tasks from specified modules.
# Ensure all modules containing tasks are listed here or tasks are imported directly.
celery_app.autodiscover_tasks(
    [
        "src.catalog.tasks",
        "src.catalog.tasks.document_tasks",
        "src.catalog.tasks.preview_tasks",
        "src.catalog.tasks.embedding_tasks",
        "src.catalog.tasks.dropbox_tasks",  # if it exists and has tasks
        "src.catalog.tasks.recovery_tasks",  # if it exists and has tasks
    ]
)  # Add other task modules if necessary

# Configure Celery
celery_app.conf.update(
    result_backend=result_backend,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Configure task routing
celery_app.conf.task_routes = {
    "catalog.tasks.process_document": {"queue": QUEUE_NAMES["DOCUMENT_PROCESSING"]},
    "src.catalog.tasks.document_tasks.process_document": {
        "queue": QUEUE_NAMES["DOCUMENT_PROCESSING"]
    },
    "src.catalog.tasks.analyze_document": {"queue": QUEUE_NAMES["ANALYSIS"]},
    "src.catalog.tasks.preview_tasks.generate_preview": {
        "queue": QUEUE_NAMES["PREVIEWS"]
    },
    "src.catalog.tasks.dropbox_tasks.sync_dropbox": {
        "queue": QUEUE_NAMES["DOCUMENT_PROCESSING"]
    },
    "src.catalog.tasks.embedding_tasks.generate_embeddings": {
        "queue": QUEUE_NAMES["DEFAULT"]
    },
    "tasks.process_batch_uploads": {
        "queue": QUEUE_NAMES["DEFAULT"]
    },  # Route for the new batch task
}

# Configure Celery Beat schedule
celery_app.conf.beat_schedule = {
    "process-batch-uploads-every-45-seconds": {
        "task": "tasks.process_batch_uploads",
        "schedule": 45.0,  # Run every 45 seconds
        "options": {"queue": QUEUE_NAMES["DEFAULT"]},  # Can specify queue here too
    },
    # Example of another periodic task (if you had one)
    # 'recover-pending-documents-hourly': {
    #     'task': 'tasks.recover_pending_documents', # Assuming you have this task defined
    #     'schedule': 3600.0, # Run every hour
    #     'options': {'queue': QUEUE_NAMES['DEFAULT']}
    # },
}

# Verify Redis connection on module import
try:
    with celery_app.connection_or_acquire() as conn:
        logger.info("Successfully connected to Redis")
except Exception as e:
    logger.error(f"Failed to connect to Redis: {str(e)}")


@celery_app.task(name="debug.list_tasks")
def list_registered_tasks():
    """List all registered tasks"""
    return list(sorted(celery_app.tasks.keys()))
