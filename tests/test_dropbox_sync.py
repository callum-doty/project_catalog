#!/usr/bin/env python3
# sync_dropbox.py

import os
import sys
import logging
from datetime import datetime
import dropbox
from minio import Minio
import tempfile
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DropboxMinIOSync:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Initialize Dropbox client
        self.dropbox_token = os.getenv('DROPBOX_ACCESS_TOKEN')
        if not self.dropbox_token:
            raise ValueError("DROPBOX_ACCESS_TOKEN environment variable is not set")
        self.dbx = dropbox.Dropbox(self.dropbox_token)
        self.dropbox_folder = os.getenv('DROPBOX_FOLDER_PATH', '/documents')
        
        # Initialize MinIO client
        self.minio_client = Minio(
            endpoint="minio:9000",
            access_key=os.getenv('MINIO_ACCESS_KEY', 'minioaccess'),
            secret_key=os.getenv('MINIO_SECRET_KEY', 'miniosecret'),
            secure=False
        )
        
        self.bucket_name = 'documents'
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """Ensure the MinIO bucket exists"""
        try:
            if not self.minio_client.bucket_exists(self.bucket_name):
                self.minio_client.make_bucket(self.bucket_name)
                logger.info(f"Created bucket: {self.bucket_name}")
        except Exception as e:
            logger.error(f"Error checking/creating bucket: {str(e)}")
            raise

    def _get_existing_files(self):
        """Get list of files already in MinIO"""
        try:
            existing_files = set()
            objects = self.minio_client.list_objects(self.bucket_name)
            for obj in objects:
                existing_files.add(obj.object_name)
            return existing_files
        except Exception as e:
            logger.error(f"Error listing MinIO objects: {str(e)}")
            return set()

    def sync_files(self):
        """Sync files from Dropbox to MinIO"""
        try:
            # Get existing files in MinIO
            existing_files = self._get_existing_files()
            logger.info(f"Found {len(existing_files)} existing files in MinIO")

            # List files in Dropbox folder
            result = self.dbx.files_list_folder(self.dropbox_folder)
            new_files = 0
            skipped_files = 0

            for entry in result.entries:
                if isinstance(entry, dropbox.files.FileMetadata):
                    if entry.name in existing_files:
                        logger.info(f"Skipping existing file: {entry.name}")
                        skipped_files += 1
                        continue

                    try:
                        logger.info(f"Processing new file: {entry.name}")
                        
                        # Download file from Dropbox
                        _, response = self.dbx.files_download(entry.path_display)
                        
                        # Create temporary file
                        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                            temp_file.write(response.content)
                            temp_path = temp_file.name

                        try:
                            # Upload to MinIO
                            self.minio_client.fput_object(
                                self.bucket_name,
                                entry.name,
                                temp_path
                            )
                            new_files += 1
                            logger.info(f"Successfully uploaded: {entry.name}")
                            
                        finally:
                            # Clean up temporary file
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                                
                    except Exception as e:
                        logger.error(f"Error processing file {entry.name}: {str(e)}")
                        continue

            logger.info(f"Sync completed: {new_files} files uploaded, {skipped_files} files skipped")
            return new_files, skipped_files

        except Exception as e:
            logger.error(f"Sync error: {str(e)}")
            raise

def main():
    try:
        syncer = DropboxMinIOSync()
        new_files, skipped_files = syncer.sync_files()
        logger.info("Sync process completed successfully")
        return 0
    except Exception as e:
        logger.error(f"Sync process failed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())