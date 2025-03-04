# app/services/storage_service.py
import os
import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class FileSystemStorage:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FileSystemStorage, cls).__new__(cls)
            cls._instance._init_storage()
        return cls._instance
    
    def _init_storage(self):
        # Define storage directory
        self.storage_dir = os.getenv("STORAGE_DIR", "./storage")
        self.bucket = os.getenv("STORAGE_BUCKET", "documents")
        self.bucket_path = os.path.join(self.storage_dir, self.bucket)
        
        # Ensure storage directories exist
        Path(self.bucket_path).mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized file system storage at {self.bucket_path}")
    
    def upload_file(self, filepath, filename):
        """Copy file to storage directory"""
        try:
            destination = os.path.join(self.bucket_path, filename)
            shutil.copy2(filepath, destination)
            logger.info(f"Uploaded file to {destination}")
            return f"{self.bucket}/{filename}"
        except Exception as e:
            logger.error(f"Upload failed: {str(e)}")
            raise Exception(f"Storage upload failed: {str(e)}")

    def get_file(self, filename):
        """Get file data from storage"""
        try:
            file_path = os.path.join(self.bucket_path, filename)
            with open(file_path, 'rb') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read file {filename}: {str(e)}")
            raise Exception(f"Storage read failed: {str(e)}")

    def download_file(self, filename, download_path):
        """Copy file from storage to a local path"""
        try:
            source = os.path.join(self.bucket_path, filename)
            shutil.copy2(source, download_path)
            return download_path
        except Exception as e:
            logger.error(f"Download failed: {str(e)}")
            raise Exception(f"Storage download failed: {str(e)}")

# For backward compatibility
MinIOStorage = FileSystemStorage