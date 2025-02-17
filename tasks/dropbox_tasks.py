# tasks/dropbox_tasks.py

from .celery_app import celery_app, logger

@celery_app.task(name='tasks.dropbox_tasks.sync_dropbox')
def sync_dropbox():
    """Sync files from Dropbox folder"""
    logger.info("=== Starting Dropbox sync task ===")
    
    # Import here to avoid circular imports
    from app import create_app
    from app.services.dropbox_service import DropboxService
    from .document_tasks import process_document
    
    # Create Flask app instance
    app = create_app()
    
    # Use app context for database operations
    with app.app_context():
        try:
            dropbox_service = DropboxService()
            
            # Test connection
            connection_status = dropbox_service.test_connection()
            
            if not connection_status.get('connected'):
                logger.error(f"Dropbox connection failed: {connection_status.get('error')}")
                return False
                
            # List and process new files
            new_files = dropbox_service.list_new_files()
            
            if not new_files:
                logger.info("No new files to process")
                return "No new files found"
            
            processed_count = 0
            for file_metadata in new_files:
                try:
                    logger.info(f"Processing file: {file_metadata.name}")
                    document, minio_path = dropbox_service.process_file(file_metadata)
                    
                    if document and minio_path:
                        process_document.delay(document.filename, minio_path, document.id)
                        processed_count += 1
                        
                except Exception as e:
                    logger.error(f"Error processing file {file_metadata.name}: {str(e)}", exc_info=True)

            result_message = f"Processed {processed_count} out of {len(new_files)} new files"
            logger.info(f"=== Sync task complete: {result_message} ===")
            return result_message
            
        except Exception as e:
            logger.error(f"Error in Dropbox sync task: {str(e)}", exc_info=True)
            raise