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
import json

@celery_app.task(name='tasks.sync_dropbox', bind=True)
def sync_dropbox(self):
    """Sync files from Dropbox folder"""
    logger.info("=== Starting Dropbox sync task ===")
    
    # Create Flask app instance
    app = create_app()
    
    # Use app context for database operations
    with app.app_context():
        try:
            # Print debug info about environment variables
            dropbox_token = os.getenv('DROPBOX_ACCESS_TOKEN', 'NOT_SET')
            dropbox_folder = os.getenv('DROPBOX_FOLDER_PATH', '')
            
            logger.info(f"DROPBOX_ACCESS_TOKEN exists: {'Yes' if dropbox_token != 'NOT_SET' else 'No'}")
            logger.info(f"DROPBOX_FOLDER_PATH value: '{dropbox_folder}'")
            
            logger.info("Initializing DropboxService")
            
            try:
                dropbox_service = DropboxService()
            except Exception as e:
                logger.error(f"Failed to initialize DropboxService: {str(e)}")
                logger.error(traceback.format_exc())
                return {"status": "error", "message": f"Failed to initialize DropboxService: {str(e)}"}
            
            # Test connection and folder content first
            logger.info("Testing Dropbox connection and folder contents")
            try:
                # Get account info
                account = dropbox_service.dbx.users_get_current_account()
                logger.info(f"Connected to Dropbox account: {account.email}")
                
                # List root folder contents to debug
                root_contents = dropbox_service.dbx.files_list_folder("")
                logger.info(f"Root folder has {len(root_contents.entries)} entries")
                
                # Log the first few entries to check what's there
                for idx, entry in enumerate(root_contents.entries[:5]):
                    if hasattr(entry, 'name'):
                        logger.info(f"Root entry {idx}: {entry.name} (Type: {type(entry).__name__})")
                
                # If a subfolder is specified, check its contents too
                if dropbox_folder:
                    try:
                        folder_contents = dropbox_service.dbx.files_list_folder(dropbox_folder)
                        logger.info(f"Specified folder '{dropbox_folder}' has {len(folder_contents.entries)} entries")
                    except Exception as e:
                        logger.error(f"Error listing specified folder '{dropbox_folder}': {str(e)}")
                
                connection_status = {
                    'connected': True,
                    'account_email': account.email,
                    'folder_path': dropbox_service.folder_path
                }
            except Exception as e:
                logger.error(f"Connection test failed: {str(e)}")
                logger.error(traceback.format_exc())
                connection_status = {
                    'connected': False,
                    'error': str(e)
                }
            
            logger.info(f"Connection status: {json.dumps(connection_status)}")
            
            if not connection_status.get('connected'):
                logger.error(f"Dropbox connection failed: {connection_status.get('error')}")
                return {"status": "error", "message": f"Dropbox connection failed: {connection_status.get('error')}"}
                
            logger.info(f"Connected to Dropbox account: {connection_status.get('account_email')}")
            logger.info(f"Using folder path: {dropbox_service.folder_path}")
            
            # List and process new files
            logger.info("Listing new files from Dropbox")
            
            try:
                # Get processed file IDs from database
                processed_files = {sync.dropbox_file_id 
                                for sync in DropboxSync.query.all()}
                logger.info(f"Found {len(processed_files)} already processed files in database")
                
                # List new files directly here for more control
                new_files = []
                
                # Get all files from the root folder or specified folder
                result = dropbox_service.dbx.files_list_folder(
                    dropbox_service.folder_path,
                    recursive=True
                )
                
                # Process entries
                for entry in result.entries:
                    if hasattr(entry, 'path_lower') and hasattr(entry, 'id'):
                        logger.info(f"Found: {entry.path_lower} (ID: {entry.id})")
                        
                        # Check if it's a file and not already processed
                        if hasattr(entry, 'size') and entry.id not in processed_files:
                            # Check if it's a supported file type
                            path_lower = entry.path_lower
                            if (path_lower.endswith('.pdf') or path_lower.endswith('.jpg') or 
                                path_lower.endswith('.jpeg') or path_lower.endswith('.png')):
                                new_files.append(entry)
                                logger.info(f"Added for processing: {entry.path_lower}")
                            else:
                                logger.info(f"Skipping unsupported file type: {entry.path_lower}")
                
                # Get additional pages if there are more results
                while result.has_more:
                    logger.info("Fetching more files...")
                    result = dropbox_service.dbx.files_list_folder_continue(result.cursor)
                    
                    for entry in result.entries:
                        if hasattr(entry, 'path_lower') and hasattr(entry, 'id'):
                            logger.info(f"Found: {entry.path_lower} (ID: {entry.id})")
                            
                            # Check if it's a file and not already processed
                            if hasattr(entry, 'size') and entry.id not in processed_files:
                                # Check if it's a supported file type
                                path_lower = entry.path_lower
                                if (path_lower.endswith('.pdf') or path_lower.endswith('.jpg') or 
                                    path_lower.endswith('.jpeg') or path_lower.endswith('.png')):
                                    new_files.append(entry)
                                    logger.info(f"Added for processing: {entry.path_lower}")
                                else:
                                    logger.info(f"Skipping unsupported file type: {entry.path_lower}")
                
                logger.info(f"Found {len(new_files)} new files to process")
                
                if not new_files:
                    logger.info("No new files to process")
                    return {"status": "success", "message": "No new files found"}
                
            except Exception as e:
                logger.error(f"Error listing Dropbox files: {str(e)}")
                logger.error(traceback.format_exc())
                return {"status": "error", "message": f"Error listing Dropbox files: {str(e)}"}
            
            # Process new files
            processed_count = 0
            error_count = 0
            
            for file_metadata in new_files:
                temp_file = None
                try:
                    # Use file name from path display or path lower
                    file_name = getattr(file_metadata, 'name', 
                                       os.path.basename(getattr(file_metadata, 'path_display', 
                                                              getattr(file_metadata, 'path_lower', 'unknown'))))
                    
                    logger.info(f"Processing file: {file_name} (Path: {file_metadata.path_lower})")
                    
                    # Download file from Dropbox to temp file
                    with tempfile.NamedTemporaryFile(delete=False) as temp:
                        temp_file = temp.name
                        
                    logger.info(f"Downloading file to: {temp_file}")
                    
                    # Make sure path_display exists
                    path_to_download = getattr(file_metadata, 'path_display', 
                                            getattr(file_metadata, 'path_lower', None))
                    
                    if not path_to_download:
                        logger.error(f"No valid path found for file: {file_name}")
                        error_count += 1
                        continue
                        
                    dropbox_service.dbx.files_download_to_file(temp_file, path_to_download)
                    
                    if not os.path.exists(temp_file) or os.path.getsize(temp_file) == 0:
                        logger.error(f"Downloaded file is empty or doesn't exist: {temp_file}")
                        error_count += 1
                        continue
                    
                    logger.info(f"Successfully downloaded file: {file_name} (Size: {os.path.getsize(temp_file)} bytes)")
                    
                    # Create document record
                    document = Document(
                        filename=file_name,
                        upload_date=datetime.utcnow(),
                        file_size=os.path.getsize(temp_file),
                        status=TASK_STATUSES['PENDING'],
                        page_count=1
                    )
                    db.session.add(document)
                    db.session.flush()
                    logger.info(f"Created document record with ID: {document.id}")
                    
                    # Store in MinIO
                    from app.services.storage_service import MinIOStorage
                    storage = MinIOStorage()
                    
                    try:
                        minio_path = storage.upload_file(temp_file, file_name)
                        logger.info(f"Uploaded to MinIO: {minio_path}")
                    except Exception as e:
                        logger.error(f"MinIO upload failed: {str(e)}")
                        logger.error(traceback.format_exc())
                        db.session.rollback()
                        error_count += 1
                        continue
                    
                    # Create sync record
                    sync_record = DropboxSync(
                        document_id=document.id,
                        dropbox_file_id=file_metadata.id,
                        dropbox_path=path_to_download,
                        sync_date=datetime.utcnow(),
                        status='SYNCED'
                    )
                    db.session.add(sync_record)
                    db.session.commit()
                    logger.info(f"Created sync record for file: {file_name}")
                    
                    # Trigger processing
                    from .document_tasks import process_document
                    task = process_document.delay(file_name, minio_path, document.id)
                    logger.info(f"Triggered processing task with ID: {task.id}")
                    
                    logger.info(f"Successfully processed file: {file_name}")
                    processed_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing file {getattr(file_metadata, 'name', 'unknown')}: {str(e)}")
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
            
            logger.info(f"=== Sync task complete: {json.dumps(result)} ===")
            return result
            
        except Exception as e:
            logger.error(f"Error in Dropbox sync task: {str(e)}")
            logger.error(traceback.format_exc())
            return {"status": "error", "message": f"Dropbox sync failed: {str(e)}"}