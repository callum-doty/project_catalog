"""
Local storage service for development
Handles file storage without requiring MinIO/S3
"""

import os
import shutil
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class LocalStorageService:
    """Local file storage service for development"""
    
    def __init__(self, storage_path: str = "./dev_storage"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        logger.info(f"Initialized local storage at: {self.storage_path}")
    
    def get_file(self, filename: str) -> Optional[bytes]:
        """Get file content as bytes"""
        try:
            file_path = self.storage_path / filename
            if file_path.exists():
                return file_path.read_bytes()
            else:
                logger.warning(f"File not found: {filename}")
                return None
        except Exception as e:
            logger.error(f"Error reading file {filename}: {e}")
            return None
    
    def upload_file(self, local_path: str, filename: str) -> str:
        """Upload file to local storage"""
        try:
            source = Path(local_path)
            destination = self.storage_path / filename
            
            shutil.copy2(source, destination)
            logger.info(f"Uploaded file: {filename}")
            return str(destination)
        except Exception as e:
            logger.error(f"Error uploading file {filename}: {e}")
            raise
    
    def get_presigned_url(self, filename: str, bucket_name: str = None) -> Optional[str]:
        """Get URL for file access (for local development, return file path)"""
        file_path = self.storage_path / filename
        if file_path.exists():
            return f"/api/files/{filename}"
        return None
    
    def file_exists(self, filename: str) -> bool:
        """Check if file exists"""
        return (self.storage_path / filename).exists()
