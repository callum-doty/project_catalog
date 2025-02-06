# app/services/dropbox_service.py

import os
import dropbox
from datetime import datetime
from app.models.models import Document, DropboxSync
from app.extensions import db
from app.services.storage_service import MinIOStorage

class DropboxService:
    def __init__(self):
        self.access_token = os.getenv('DROPBOX_ACCESS_TOKEN')
        self.dbx = dropbox.Dropbox(self.access_token)
        self.folder_path = os.getenv('DROPBOX_FOLDER_PATH', '/documents')
        self.storage = MinIOStorage()

    def list_new_files(self):
        """List files in Dropbox folder that haven't been processed"""
        try:
            # Get list of already processed files
            processed_files = {sync.dropbox_file_id 
                            for sync in DropboxSync.query.all()}

            # List files in Dropbox folder
            result = self.dbx.files_list_folder(self.folder_path)
            new_files = []

            for entry in result.entries:
                if isinstance(entry, dropbox.files.FileMetadata):
                    if entry.id not in processed_files:
                        new_files.append(entry)

            return new_files
        except Exception as e:
            print(f"Error listing Dropbox files: {str(e)}")
            return []

    def process_file(self, file_metadata):
        """Process a single file from Dropbox"""
        temp_path = None
        try:
            # Check if file was already processed
            existing_sync = DropboxSync.query.filter_by(
                dropbox_file_id=file_metadata.id
            ).first()
            if existing_sync:
                return None, None

            # Download file from Dropbox
            _, response = self.dbx.files_download(file_metadata.path_display)
            file_data = response.content
            
            # Save to temporary file
            temp_path = f"/tmp/{file_metadata.name}"
            with open(temp_path, 'wb') as f:
                f.write(file_data)

            # Upload to MinIO
            minio_path = self.storage.upload_file(temp_path, file_metadata.name)

            # Create document record
            document = Document(
                filename=file_metadata.name,
                upload_date=datetime.utcnow(),
                file_size=file_metadata.size,
                status='PENDING',
                page_count=1  # This will be updated during processing
            )
            db.session.add(document)
            db.session.flush()  # Get the document ID

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

            return document, minio_path

        except Exception as e:
            print(f"Error processing Dropbox file {file_metadata.name}: {str(e)}")
            db.session.rollback()
            return None, None
        finally:
            # Clean up temp file if it exists
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)