# tasks/dropbox_tasks.py

from celery import shared_task
from .celery_app import celery_app
from .utils import logger, TASK_STATUSES
from app.services.dropbox_service import DropboxService
from app.models.models import Document, DropboxSync
from app.extensions import db
from app import create_app
import os
import tempfile
from datetime import datetime
import traceback

@celery_app.task(name='tasks.sync_dropbox', bind=True)
def sync_dropbox(self):
    """Sync files from Dropbox folder"""
    logger.info("=== Starting Dropbox sync task ===")
    
    # Create Flask app instance
    app = create_app()
    
    # Use app context for database operations
    with app.app_context():
        try:
            logger.info("Initializing DropboxService")
            
            try:
                dropbox_service = DropboxService()
            except Exception as e:
                logger.error(f"Failed to initialize DropboxService: {str(e)}")
                return {"status": "error", "message": f"Failed to initialize DropboxService: {str(e)}"}
            
            # Test connection first
            logger.info("Testing Dropbox connection")
            try:
                account = dropbox_service.dbx.users_get_current_account()
                connection_status = {
                    'connected': True,
                    'account_email': account.email,
                    'folder_path': dropbox_service.folder_path
                }
            except Exception as e:
                logger.error(f"Connection test failed: {str(e)}")
                connection_status = {
                    'connected': False,
                    'error': str(e)
                }
            
            logger.info(f"Connection status: {connection_status}")
            
            if not connection_status.get('connected'):
                logger.error(f"Dropbox connection failed: {connection_status.get('error')}")
                return {"status": "error", "message": f"Dropbox connection failed: {connection_status.get('error')}"}
                
            logger.info(f"Connected to Dropbox account: {connection_status.get('account_email')}")
            logger.info(f"Using folder path: {dropbox_service.folder_path}")
            
            # List and process new files
            logger.info("Listing new files from Dropbox")
            
            try:
                new_files = dropbox_service.list_new_files()
                logger.info(f"Found {len(new_files)} new files in Dropbox")
            except Exception as e:
                logger.error(f"Error listing Dropbox files: {str(e)}", exc_info=True)
                return {"status": "error", "message": f"Error listing Dropbox files: {str(e)}"}
            
            if not new_files:
                logger.info("No new files to process")
                return {"status": "success", "message": "No new files found"}
            
            # Log file details
            for file in new_files:
                logger.info(f"Found file: {file.name} (Path: {file.path_display}, Size: {file.size} bytes)")
            
            processed_count = 0
            error_count = 0
            
            for file_metadata in new_files:
                temp_file = None
                try:
                    # Check if this file was already processed
                    existing = DropboxSync.query.filter_by(dropbox_file_id=file_metadata.id).first()
                    if existing:
                        logger.info(f"Skipping already processed file: {file_metadata.name}")
                        continue
                    
                    logger.info(f"Processing file: {file_metadata.name}")
                    
                    # Download file from Dropbox to temp file
                    with tempfile.NamedTemporaryFile(delete=False) as temp:
                        temp_file = temp.name
                        
                    logger.info(f"Downloading file to: {temp_file}")
                    dropbox_service.dbx.files_download_to_file(temp_file, file_metadata.path_display)
                    
                    if not os.path.exists(temp_file) or os.path.getsize(temp_file) == 0:
                        logger.error(f"Downloaded file is empty or doesn't exist: {temp_file}")
                        error_count += 1
                        continue
                    
                    logger.info(f"Successfully downloaded file: {file_metadata.name} (Size: {os.path.getsize(temp_file)} bytes)")
                    
                    # Create document record
                    document = Document(
                        filename=file_metadata.name,
                        upload_date=datetime.utcnow(),
                        file_size=os.path.getsize(temp_file),
                        status=TASK_STATUSES['PENDING'],
                        page_count=1
                    )
                    db.session.add(document)
                    db.session.flush()
                    
                    # Store in MinIO
                    from app.services.storage_service import MinIOStorage
                    storage = MinIOStorage()
                    
                    try:
                        minio_path = storage.upload_file(temp_file, file_metadata.name)
                        logger.info(f"Uploaded to MinIO: {minio_path}")
                    except Exception as e:
                        logger.error(f"MinIO upload failed: {str(e)}")
                        db.session.rollback()
                        error_count += 1
                        continue
                    
                    # Create sync record
                    sync_record = DropboxSync(
                        document_id=document.id,
                        dropbox_file_id=file_metadata.id,
                        dropbox_path=file_metadata.path_display,
                        sync_date=datetime.utcnow(),
                        status='SYNCED'
                    )
                    db.session.add(sync_record)
                    db.session.commit()
                    
                    # Trigger processing
                    from .document_tasks import process_document
                    process_document.delay(file_metadata.name, minio_path, document.id)
                    
                    logger.info(f"Successfully processed file: {file_metadata.name}")
                    processed_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing file {file_metadata.name}: {str(e)}")
                    logger.error(traceback.format_exc())
                    db.session.rollback()
                    error_count += 1
                finally:
                    # Clean up temp file
                    if temp_file and os.path.exists(temp_file):
                        os.remove(temp_file)
                        logger.debug(f"Cleaned up temporary file: {temp_file}")

            result = {
                "status": "success",
                "processed": processed_count,
                "errors": error_count,
                "total": len(new_files),
                "message": f"Processed {processed_count} out of {len(new_files)} files. Errors: {error_count}"
            }
            
            logger.info(f"=== Sync task complete: {result['message']} ===")
            return result
            
        except Exception as e:
            logger.error(f"Error in Dropbox sync task: {str(e)}", exc_info=True)
            return {"status": "error", "message": f"Dropbox sync failed: {str(e)}"}