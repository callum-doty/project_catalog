# tasks/dropbox_tasks.py

from celery import shared_task
from celery.utils.log import get_task_logger
from app.services.dropbox_service import DropboxService
from tasks.document_tasks import process_document
import os

logger = get_task_logger(__name__)

@shared_task(name='tasks.sync_dropbox')
def sync_dropbox():
    """Sync files from Dropbox folder"""
    logger.info("Starting Dropbox sync task")
    logger.info(f"Dropbox token: {'Present' if os.getenv('DROPBOX_ACCESS_TOKEN') else 'Missing'}")
    logger.info(f"Dropbox folder path: {os.getenv('DROPBOX_FOLDER_PATH', '/documents')}")
    
    try:
        dropbox_service = DropboxService()
        new_files = dropbox_service.list_new_files()
        logger.info(f"Found {len(new_files)} new files in Dropbox")
        
        for file_metadata in new_files:
            try:
                logger.info(f"Processing file: {file_metadata.name}")
                document, minio_path = dropbox_service.process_file(file_metadata)
                if document and minio_path:
                    logger.info(f"Successfully processed {file_metadata.name}, queuing for analysis")
                    process_document.delay(document.filename, minio_path, document.id)
                else:
                    logger.error(f"Failed to process {file_metadata.name}")
            except Exception as e:
                logger.error(f"Error processing file {file_metadata.name}: {str(e)}", exc_info=True)

        return f"Processed {len(new_files)} new files"
    except Exception as e:
        logger.error(f"Error in Dropbox sync task: {str(e)}", exc_info=True)
        raise