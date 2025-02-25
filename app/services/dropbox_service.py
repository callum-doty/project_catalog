# app/services/dropbox_service.py

import os
import logging
from datetime import datetime
import dropbox
from dropbox.exceptions import ApiError, AuthError, RateLimitError
from app.models.models import Document, DropboxSync
from app.extensions import db
from app.services.storage_service import MinIOStorage

logger = logging.getLogger(__name__)

class DropboxService:
    def __init__(self):
        self.access_token = os.getenv('DROPBOX_ACCESS_TOKEN')
        if not self.access_token:
            logger.error("DROPBOX_ACCESS_TOKEN not set")
            raise ValueError("DROPBOX_ACCESS_TOKEN not set")
            
        try:
            # Initialize with shorter timeout for faster error detection
            self.dbx = dropbox.Dropbox(
                self.access_token,
                timeout=10
            )
            # Test authentication
            logger.info("Request to users/get_current_account")
            self.dbx.users_get_current_account()
            logger.info("Successfully connected to Dropbox")
            
        except AuthError as e:
            logger.error(f"Dropbox authentication failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Dropbox initialization error: {str(e)}")
            raise

        self.folder_path = os.getenv('DROPBOX_FOLDER_PATH', '/test')
        self.storage = MinIOStorage()

    def test_connection(self):
        """Test Dropbox connection and return status"""
        try:
            account = self.dbx.users_get_current_account()
            # Test folder access
            try:
                self.dbx.files_list_folder(self.folder_path)
                return {
                    'connected': True,
                    'account_email': account.email,
                    'folder_path': self.folder_path
                }
            except ApiError as e:
                if e.error.is_path() and e.error.get_path().is_not_found():
                    logger.error(f"Folder not found: {self.folder_path}")
                    return {
                        'connected': False,
                        'error': f"Folder not found: {self.folder_path}"
                    }
                return {
                    'connected': False,
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

    def get_sync_status(self):
        """Get the current sync status for Dropbox integration"""
        from datetime import datetime, timedelta
        from app.models.models import DropboxSync, Document
        from sqlalchemy import func
        
        try:
            # Test connection first
            try:
                connection_status = self.test_connection()
                dropbox_connected = connection_status.get('connected', False)
            except Exception as e:
                logger.error(f"Dropbox connection test failed: {str(e)}")
                dropbox_connected = False
            
            # Get the latest sync record
            latest_sync = DropboxSync.query.order_by(DropboxSync.sync_date.desc()).first()
            
            # Get count of synced files in last 24 hours
            yesterday = datetime.utcnow() - timedelta(days=1)
            recent_syncs = DropboxSync.query.filter(DropboxSync.sync_date >= yesterday).count()
            
            status = {
                'last_sync_time': latest_sync.sync_date.isoformat() if latest_sync else None,
                'last_status': latest_sync.status if latest_sync else None,
                'last_24h_files': recent_syncs,
                'dropbox_connected': dropbox_connected
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting Dropbox sync status: {str(e)}")
            return {
                'last_sync_time': None,
                'last_status': 'ERROR',
                'last_24h_files': 0,
                'dropbox_connected': False
            }

    def list_new_files(self):
        """List files in Dropbox folder that haven't been processed"""
        try:
            # Get list of already processed files
            processed_files = {sync.dropbox_file_id 
                            for sync in DropboxSync.query.all()}
            
            logger.info(f"Found {len(processed_files)} previously processed files")
            
            new_files = []
            try:
                logger.info(f"Listing files in folder: {self.folder_path}")
                result = self.dbx.files_list_folder(
                    self.folder_path,
                    recursive=True
                )
                
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
                                
                # Handle pagination
                while result.has_more:
                    logger.info("Fetching more files...")
                    result = self.dbx.files_list_folder_continue(result.cursor)
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
                
            except ApiError as e:
                if e.error.is_path() and e.error.get_path().is_not_found():
                    logger.error(f"Folder not found: {self.folder_path}")
                raise
                
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
            
            # Download file from Dropbox with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    _, response = self.dbx.files_download(file_metadata.path_display)
                    file_data = response.content
                    break
                except RateLimitError as e:
                    if attempt == max_retries - 1:
                        raise
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Rate limit hit, waiting {wait_time}s...")
                    import time
                    time.sleep(wait_time)
            
            # Save to temporary file
            temp_path = f"/tmp/{file_metadata.name}"
            with open(temp_path, 'wb') as f:
                f.write(file_data)

            # Upload to MinIO
            minio_path = self.storage.upload_file(temp_path, file_metadata.name)
            logger.info(f"Uploaded to MinIO: {minio_path}")

            # Create document record
            document = Document(
                filename=file_metadata.name,
                upload_date=datetime.utcnow(),
                file_size=file_metadata.size,
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


    