# app/services/dropbox_service.py

import os
import logging
from datetime import datetime, timedelta
import dropbox
from dropbox.exceptions import ApiError, AuthError, RateLimitError
from app.models.models import Document, DropboxSync
from app.extensions import db
import tempfile
import time

logger = logging.getLogger(__name__)

class DropboxService:
    def __init__(self):
        # Get access token with fallback
        self.access_token = os.getenv('DROPBOX_ACCESS_TOKEN')
        if not self.access_token:
            logger.error("DROPBOX_ACCESS_TOKEN not set")
            raise ValueError("DROPBOX_ACCESS_TOKEN environment variable is not set")
            
        # Get folder path with fallback
        self.folder_path = os.getenv('DROPBOX_FOLDER_PATH', '')
        if not self.folder_path:
            logger.warning("DROPBOX_FOLDER_PATH not set, using root folder")
            self.folder_path = ""
        
        # Normalize folder path
        if self.folder_path and not self.folder_path.startswith('/'):
            self.folder_path = f"/{self.folder_path}"
            
        logger.info(f"Initializing Dropbox with folder path: {self.folder_path}")
        
        # Initialize with retry logic
        max_retries = 3
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                self.dbx = dropbox.Dropbox(
                    self.access_token,
                    timeout=30
                )
                # Test auth immediately
                self.dbx.users_get_current_account()
                logger.info("Successfully connected to Dropbox")
                return
            except AuthError as e:
                # Auth errors mean retrying won't help
                logger.error(f"Dropbox authentication failed: {str(e)}")
                raise
            except Exception as e:
                last_error = e
                retry_count += 1
                wait_time = 2 ** retry_count  # Exponential backoff
                logger.warning(f"Dropbox initialization attempt {retry_count} failed: {str(e)}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
        
        # If we reached here, all retries failed
        logger.error(f"Failed to initialize Dropbox after {max_retries} attempts: {str(last_error)}")
        raise last_error

    def test_connection(self):
        """Test Dropbox connection and return status"""
        try:
            account = self.dbx.users_get_current_account()
            
            # Test folder access
            try:
                folder_result = self.dbx.files_list_folder(self.folder_path)
                
                # Check if folder exists but is empty
                if not folder_result.entries:
                    logger.warning(f"Folder exists but is empty: {self.folder_path}")
                
                return {
                    'connected': True,
                    'account_email': account.email,
                    'folder_path': self.folder_path,
                    'folder_exists': True,
                    'file_count': len(folder_result.entries)
                }
            except ApiError as e:
                if e.error.is_path() and e.error.get_path().is_not_found():
                    logger.error(f"Folder not found: {self.folder_path}")
                    return {
                        'connected': True,
                        'account_email': account.email,
                        'folder_exists': False,
                        'error': f"Folder not found: {self.folder_path}"
                    }
                return {
                    'connected': True,
                    'account_email': account.email,
                    'folder_exists': False,
                    'error': str(e)
                }
        except AuthError as e:
            return {
                'connected': False,
                'error': f"Authentication failed: {str(e)}"
            }
        except Exception as e:
            return {
                'connected': False,
                'error': str(e)
            }

    def list_new_files(self):
        """List files in Dropbox folder that haven't been processed"""
        try:
            # Get list of already processed files
            processed_files = {sync.dropbox_file_id 
                            for sync in DropboxSync.query.all()}
            
            logger.info(f"Found {len(processed_files)} previously processed files")
            
            new_files = []
            
            # Handle retry logic for the initial list_folder call
            max_retries = 3
            retry_count = 0
            result = None
            
            while retry_count < max_retries and result is None:
                try:
                    logger.info(f"Listing files in folder: {self.folder_path}")
                    result = self.dbx.files_list_folder(
                        self.folder_path,
                        recursive=True
                    )
                except RateLimitError:
                    retry_count += 1
                    wait_time = 2 ** retry_count
                    logger.warning(f"Rate limit hit, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                except Exception as e:
                    logger.error(f"Error listing folder: {str(e)}")
                    raise
            
            if result is None:
                logger.error("Failed to list folder after multiple attempts")
                return []
                
            # Process the results
            for entry in result.entries:
                if isinstance(entry, dropbox.files.FileMetadata):
                    logger.info(f"Found file: {entry.name} (ID: {entry.id})")
                    if entry.id not in processed_files:
                        logger.info(f"File {entry.name} is new")
                        if entry.name.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png')):
                            new_files.append(entry)
                            logger.info(f"Added {entry.name} to process list")
                        else:
                            logger.info(f"Skipping {entry.name} - unsupported file type")
                            
            # Handle pagination with retry logic
            while result.has_more:
                retry_count = 0
                next_result = None
                
                while retry_count < max_retries and next_result is None:
                    try:
                        logger.info("Fetching more files...")
                        next_result = self.dbx.files_list_folder_continue(result.cursor)
                    except RateLimitError:
                        retry_count += 1
                        wait_time = 2 ** retry_count
                        logger.warning(f"Rate limit hit, retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    except Exception as e:
                        logger.error(f"Error fetching more files: {str(e)}")
                        break
                
                if next_result is None:
                    logger.error("Failed to continue listing folder after multiple attempts")
                    break
                    
                result = next_result
                
                # Process additional results
                for entry in result.entries:
                    if isinstance(entry, dropbox.files.FileMetadata):
                        logger.info(f"Found file: {entry.name} (ID: {entry.id})")
                        if entry.id not in processed_files:
                            logger.info(f"File {entry.name} is new")
                            if entry.name.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png')):
                                new_files.append(entry)
                                logger.info(f"Added {entry.name} to process list")
                            else:
                                logger.info(f"Skipping {entry.name} - unsupported file type")
            
            logger.info(f"Total new files found: {len(new_files)}")
            return new_files
                
        except Exception as e:
            logger.error(f"Error listing Dropbox files: {str(e)}")
            raise

    def process_file(self, file_metadata):
        """Process a single file from Dropbox"""
        temp_path = None
        try:
            # Check if file was already processed
            existing_sync = DropboxSync.query.filter_by(
                dropbox_file_id=file_metadata.id
            ).first()
            
            if existing_sync:
                logger.info(f"File already processed: {file_metadata.name}")
                return None, None

            logger.info(f"Starting to process file: {file_metadata.name}")
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False) as temp:
                temp_path = temp.name
            
            # Download file from Dropbox with retry logic
            max_retries = 3
            success = False
            
            for attempt in range(max_retries):
                try:
                    self.dbx.files_download_to_file(temp_path, file_metadata.path_display)
                    
                    # Verify download was successful
                    if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                        logger.info(f"Successfully downloaded file to {temp_path} (Size: {os.path.getsize(temp_path)} bytes)")
                        success = True
                        break
                    else:
                        logger.warning(f"Download seems to have failed - empty or missing file at {temp_path}")
                except RateLimitError:
                    if attempt == max_retries - 1:
                        raise
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Rate limit hit, waiting {wait_time}s...")
                    time.sleep(wait_time)
                except Exception as e:
                    logger.error(f"Download attempt {attempt+1} failed: {str(e)}")
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(2 ** attempt)
            
            if not success:
                raise Exception(f"Failed to download file after {max_retries} attempts")

            # Upload to MinIO
            from app.services.storage_service import MinIOStorage
            storage = MinIOStorage()
            minio_path = storage.upload_file(temp_path, file_metadata.name)
            logger.info(f"Uploaded to MinIO: {minio_path}")

            # Create document record
            document = Document(
                filename=file_metadata.name,
                upload_date=datetime.utcnow(),
                file_size=os.path.getsize(temp_path),
                status='PENDING',
                page_count=1
            )
            db.session.add(document)
            db.session.flush()

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
            
            logger.info(f"Successfully processed file: {file_metadata.name}")
            return document, minio_path

        except Exception as e:
            logger.error(f"Error processing file {file_metadata.name}: {str(e)}")
            db.session.rollback()
            raise
        finally:
            # Clean up temp file
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
                logger.debug(f"Cleaned up temporary file: {temp_path}")
    
    def get_sync_status(self):
        """Get information about recent syncs"""
        try:
            # Get most recent sync
            last_sync = DropboxSync.query.order_by(DropboxSync.sync_date.desc()).first()
            
            # Get count of files synced in last 24 hours
            yesterday = datetime.utcnow() - timedelta(days=1)
            recent_syncs = DropboxSync.query.filter(DropboxSync.sync_date >= yesterday).count()
            
            # Test connection status
            connection_status = self.test_connection()
            
            return {
                'last_sync_time': last_sync.sync_date if last_sync else None,
                'last_24h_files': recent_syncs,
                'last_status': 'SUCCESS',
                'dropbox_connected': connection_status.get('connected', False)
            }
        except Exception as e:
            logger.error(f"Error getting sync status: {str(e)}")
            return {
                'error': str(e),
                'last_sync_time': None,
                'last_24h_files': 0,
                'last_status': 'ERROR',
                'dropbox_connected': False
            }