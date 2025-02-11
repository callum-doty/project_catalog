# tasks/dropbox_tasks.py

from celery import shared_task
from .celery_app import celery_app
from .utils import logger
from app.services.dropbox_service import DropboxService

@celery_app.task(name='tasks.sync_dropbox', bind=True)
def sync_dropbox(self):
    """Sync files from Dropbox folder"""
    logger.info("=== Starting Dropbox sync task ===")
    
    try:
        logger.info("Initializing DropboxService")
        dropbox_service = DropboxService()
        
        # Test connection first
        logger.info("Testing Dropbox connection")
        connection_status = dropbox_service.test_connection()
        logger.info(f"Connection status: {connection_status}")
        
        if not connection_status.get('connected'):
            logger.error(f"Dropbox connection failed: {connection_status.get('error')}")
            return False
            
        logger.info(f"Connected to Dropbox account: {connection_status.get('account_email')}")
        logger.info(f"Using folder path: {dropbox_service.folder_path}")
        
        # List and process new files
        logger.info("Listing new files from Dropbox")
        new_files = dropbox_service.list_new_files()
        logger.info(f"Found {len(new_files)} new files in Dropbox")
        
        if not new_files:
            logger.info("No new files to process")
            return "No new files found"
        
        # Log file details
        for file in new_files:
            logger.info(f"Found file: {file.name} (Path: {file.path_display}, Size: {file.size} bytes)")
        
        processed_count = 0
        for file_metadata in new_files:
            try:
                logger.info(f"Processing file: {file_metadata.name}")
                document, minio_path = dropbox_service.process_file(file_metadata)
                
                if document and minio_path:
                    logger.info(f"Successfully processed {file_metadata.name}")
                    logger.info(f"MinIO path: {minio_path}")
                    logger.info(f"Document ID: {document.id}")
                    
                    # Import here to avoid circular import
                    from .document_tasks import process_document
                    process_document.delay(document.filename, minio_path, document.id)
                    processed_count += 1
                else:
                    logger.error(f"Failed to process {file_metadata.name} - no document or minio_path returned")
                    
            except Exception as e:
                logger.error(f"Error processing file {file_metadata.name}: {str(e)}", exc_info=True)

        result_message = f"Processed {processed_count} out of {len(new_files)} new files"
        logger.info(f"=== Sync task complete: {result_message} ===")
        return result_message
        
    except Exception as e:
        logger.error(f"Error in Dropbox sync task: {str(e)}", exc_info=True)
        raise self.retry(exc=e)