# app/services/storage_service.py
import os
import io
import logging
from urllib3 import PoolManager
from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)

class MinIOStorage:
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MinIOStorage, cls).__new__(cls)
            cls._instance._init_client()
        return cls._instance
    
    def _init_client(self):
        if self._client is None:
            try:
                # Configure HTTP client
                http_client = PoolManager(timeout=5.0, retries=3)
                
                # Get MinIO configuration from environment
                minio_url = os.getenv("MINIO_URL", "minio-1:9000")
                access_key = os.getenv("MINIO_ACCESS_KEY", "minioaccess")
                secret_key = os.getenv("MINIO_SECRET_KEY", "miniosecret")
                
                logger.info(f"Initializing MinIO client with endpoint: {minio_url}")
                
                # Initialize MinIO client
                self._client = Minio(
                    endpoint=minio_url,
                    access_key=access_key,
                    secret_key=secret_key,
                    secure=False,
                    http_client=http_client
                )
                
                # Set bucket name
                self.bucket = os.getenv("MINIO_BUCKET", "documents")
                
                # Test connection and ensure bucket exists
                try:
                    logger.info("Testing MinIO connection...")
                    buckets = list(self._client.list_buckets())
                    logger.info(f"Connected to MinIO. Found buckets: {[b.name for b in buckets]}")
                    
                    if not self._client.bucket_exists(self.bucket):
                        logger.info(f"Creating bucket: {self.bucket}")
                        self._client.make_bucket(self.bucket)
                        logger.info(f"Successfully created bucket: {self.bucket}")
                    else:
                        logger.info(f"Using existing bucket: {self.bucket}")
                        
                except S3Error as err:
                    logger.error(f"MinIO bucket operation failed: {str(err)}")
                    raise
                    
            except Exception as e:
                logger.error(f"Failed to initialize MinIO client: {str(e)}", exc_info=True)
                raise
    
    @property
    def client(self):
        return self._client

    def upload_file(self, filepath, filename):
        """Upload file to MinIO"""
        try:
            logger.info(f"Uploading file to MinIO: {filename}")
            logger.info(f"MinIO bucket: {self.bucket}")
            
            self.client.fput_object(
                bucket_name=self.bucket,
                object_name=filename,
                file_path=filepath
            )
            
            logger.info(f"Successfully uploaded file to MinIO: {filename}")
            return f"{self.bucket}/{filename}"
        except Exception as e:
            logger.error(f"MinIO upload failed: {str(e)}", exc_info=True)
            raise Exception(f"MinIO upload failed: {str(e)}")

    def get_file(self, filename):
        """Get file data from MinIO"""
        try:
            logger.info(f"Getting file from MinIO: {filename}")
            
            data = io.BytesIO()
            response = self.client.get_object(self.bucket, filename)
            
            for d in response.stream(32*1024):
                data.write(d)
            
            data.seek(0)
            logger.info(f"Successfully retrieved file from MinIO: {filename}")
            return data.getvalue()
        except Exception as e:
            logger.error(f"MinIO download failed: {str(e)}", exc_info=True)
            raise Exception(f"MinIO download failed: {str(e)}")

    def download_file(self, filename, download_path):
        """Download file from MinIO to a local path"""
        try:
            logger.info(f"Downloading file from MinIO: {filename} to {download_path}")
            
            self.client.fget_object(
                bucket_name=self.bucket,
                object_name=filename,
                file_path=download_path
            )
            
            logger.info(f"Successfully downloaded file from MinIO: {filename}")
            return download_path
        except Exception as e:
            logger.error(f"MinIO download failed: {str(e)}", exc_info=True)
            raise Exception(f"MinIO download failed: {str(e)}")